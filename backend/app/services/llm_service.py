import logging
import re
from typing import Any, Dict, List, Tuple
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


DEFAULT_MAX_OUTPUT_TOKENS = 2048


NIM_TIMEOUT = httpx.Timeout(timeout=10.0, connect=3.0, read=10.0, write=10.0, pool=5.0)
GEMINI_TIMEOUT = httpx.Timeout(timeout=20.0, connect=3.0, read=20.0, write=10.0, pool=5.0)


class LLMService:
    def __init__(self):
        pass

    @property
    def nim_api_key(self) -> str:
        return getattr(settings, "NVIDIA_NIM_API_KEY", "")

    @property
    def nim_base_url(self) -> str:
        return getattr(
            settings,
            "NVIDIA_NIM_BASE_URL",
            "https://integrate.api.nvidia.com/v1",
        )

    @property
    def nim_model(self) -> str:
        return getattr(
            settings,
            "NVIDIA_NIM_CHAT_MODEL",
            "meta/llama-3.1-8b-instruct",
        )

    @property
    def gemini_api_key(self) -> str:
        return getattr(settings, "GEMINI_API_KEY", "")

    @property
    def gemini_model(self) -> str:
        return getattr(
            settings,
            "GEMINI_MODEL",
            "gemini-3.6-flash",
        )

    def _prepare_rag_prompt(
        self,
        question: str,
        contexts: List[Dict[str, Any]],
        repo_meta: Dict[str, Any] = None,
    ) -> Tuple[str, str, List[Dict[str, Any]], int]:
        context_parts: List[str] = []
        citations: List[Dict[str, Any]] = []

        for context_index, context_item in enumerate(contexts):
            file_path = context_item["file_path"]
            start_line = context_item["start_line"]
            end_line = context_item["end_line"]
            symbol_name = context_item["name"]
            source_code = context_item["source_code"]

            symbol_signature = context_item.get(
                "signature",
                f"file {file_path}",
            )

            context_parts.append(
                f"\n--- Reference [{context_index + 1}]: "
                f"{file_path} "
                f"(Lines {start_line}-{end_line}) ---\n"
                f"Symbol: {symbol_name}\n"
                f"Signature: {symbol_signature}\n"
                f"Code:\n{source_code}\n"
            )

            citations.append(
                {
                    "id": f"cite-{context_index + 1}",
                    "label": (
                        f"{file_path.split('/')[-1]}:"
                        f"{start_line}-{end_line}"
                    ),
                    "filePath": file_path,
                    "startLine": start_line,
                    "endLine": end_line,
                    "symbol": symbol_name,
                }
            )

        context_string = "".join(context_parts)

        repo_name = (
            repo_meta.get("name", "Workspace")
            if repo_meta
            else "Workspace"
        )

        language = (
            repo_meta.get("language", "Multi-Language")
            if repo_meta
            else "Multi-Language"
        )

        all_files = (
            repo_meta.get("all_files", [])
            if repo_meta
            else []
        )

        word_limit_match = re.search(
            r"(?:under|in|within|max|less than|around)\s+(\d+)\s+words",
            question,
            re.IGNORECASE,
        )

        max_words = (
            int(word_limit_match.group(1))
            if word_limit_match
            else None
        )

        tree_limit = 10 if max_words else 30

        tree_overview = (
            f"Workspace: {repo_name} ({language})\n"
            f"Indexed File Tree ({len(all_files)} files):\n"
            + "\n".join(
                f"- {file_path}"
                for file_path in all_files[:tree_limit]
            )
        )

        day_filter_match = re.search(
            r"day\s*(\d+)",
            question,
            re.IGNORECASE,
        )

        if day_filter_match:
            target_day_number = day_filter_match.group(1)

            day_matching_files = [
                file_path
                for file_path in all_files
                if (
                    f"day{target_day_number}" in file_path.lower()
                    or f"day_{target_day_number}" in file_path.lower()
                    or f"day {target_day_number}" in file_path.lower()
                )
            ]

            if day_matching_files:
                tree_overview = (
                    f"Workspace: {repo_name} ({language})\n"
                    "Relevant Target Files:\n"
                    + "\n".join(
                        f"- {file_path}"
                        for file_path in day_matching_files
                    )
                )

        limit_instruction = ""
        max_output_tokens = DEFAULT_MAX_OUTPUT_TOKENS

        if max_words:
            limit_instruction = (
                "\n\n"
                f"OUTPUT LIMIT:\n"
                f"The user explicitly requested an answer under "
                f"{max_words} words.\n"
                f"Keep the final answer strictly under "
                f"{max_words} words.\n"
                f"Do not add filler, unnecessary explanations, "
                f"or redundant sections."
            )

            max_output_tokens = min(
                2048,
                max(128, int(max_words * 2.5)),
            )

        system_msg = (
            "You are a precise, senior software engineering AI Codebase Knowledge Assistant. "
            "Your role is to thoroughly explain, trace, and synthesize how the repository components "
            "work based on the provided source code context and repository structure.\n\n"
            "SYNTHESIS & FLOW INSTRUCTIONS:\n"
            "1. When the user asks to trace a flow (e.g. authentication, routing, request lifecycle, data processing), "
            "break down the complete end-to-end execution path step-by-step using the provided code references.\n"
            "2. Explain how the referenced functions, routes, helpers, middlewares, and models connect and collaborate.\n"
            "3. Ground your explanation in the specific files and line numbers provided in the context.\n"
            "4. Do not invent non-existent file paths or imaginary APIs, but do provide a coherent, comprehensive technical explanation of the mechanisms shown in the codebase.\n"
            "5. Cite the exact files, functions, and line numbers from the reference blocks throughout your explanation.\n"
            "6. Provide a direct, authoritative, and helpful answer without defensive boilerplate or generic disclaimers."
        )

        prompt = (
            "You are an AI Codebase Knowledge Assistant.\n\n"
            f"Question:\n{question}\n\n"
            f"{tree_overview}\n\n"
            "Retrieved Source Code Contexts:\n"
            f"{context_string}\n\n"
            "INSTRUCTIONS:\n"
            "1. Synthesize a comprehensive, technical answer directly answering the user's question.\n"
            "2. Step through the implementation details, functions, routes, and data flows present in the referenced files.\n"
            "3. Cite relevant file paths and line ranges where applicable.\n"
            "4. Structure your response clearly with headings or numbered steps for lifecycles and flows."
            f"{limit_instruction}"
        )

        return system_msg, prompt, citations, max_output_tokens

    async def generate_rag_response(
        self,
        question: str,
        contexts: List[Dict[str, Any]],
        repo_meta: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        if not contexts:
            return {
                "answer": "No matching source code context found in this repository.",
                "confidence": "low",
                "citations": [],
                "provider": "None",
            }

        system_msg, prompt, citations, max_output_tokens = self._prepare_rag_prompt(
            question, contexts, repo_meta
        )

        # 1. Primary provider: NVIDIA NIM (native HTTP POST)
        if (
            self.nim_api_key
            and self.nim_api_key.startswith("nvapi-")
        ):
            try:
                nim_url = f"{self.nim_base_url.rstrip('/')}/chat/completions"
                nim_headers = {
                    "Authorization": f"Bearer {self.nim_api_key}",
                    "Content-Type": "application/json",
                }
                nim_payload = {
                    "model": self.nim_model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "top_p": 0.7,
                    "max_tokens": max_output_tokens,
                }

                async with httpx.AsyncClient(timeout=NIM_TIMEOUT) as http_client:
                    nim_resp = await http_client.post(
                        nim_url,
                        json=nim_payload,
                        headers=nim_headers,
                    )

                    if nim_resp.status_code >= 400:
                        err_text = nim_resp.text
                        logger.warning(
                            "NVIDIA NIM HTTP %d Error: %s (falling back to Gemini)",
                            nim_resp.status_code,
                            err_text,
                        )
                        raise RuntimeError(
                            f"NVIDIA NIM HTTP {nim_resp.status_code}: {err_text}"
                        )

                    nim_data = nim_resp.json()
                    choices = nim_data.get("choices", [])
                    if choices:
                        answer_content = choices[0].get("message", {}).get("content", "")
                        if answer_content:
                            return {
                                "answer": answer_content,
                                "confidence": "high",
                                "citations": citations,
                                "provider": f"NVIDIA NIM ({self.nim_model})",
                            }

                    raise RuntimeError("NVIDIA NIM returned an empty response.")

            except httpx.TimeoutException as timeout_err:
                logger.warning(
                    "NVIDIA NIM Timeout (%s): request timed out after %.1fs (falling back to Gemini)",
                    type(timeout_err).__name__,
                    float(NIM_TIMEOUT.read or 10.0),
                )
            except Exception as error:
                logger.warning(
                    "NVIDIA NIM API Error (%s) (falling back to Gemini): %s",
                    type(error).__name__,
                    error or repr(error),
                )

        # 2. Fallback provider: Google Gemini (native HTTP POST)
        if (
            self.gemini_api_key
            and len(self.gemini_api_key) > 5
            and not self.gemini_api_key.startswith("your_")
        ):
            try:
                url = (
                    "https://generativelanguage.googleapis.com/"
                    f"v1beta/models/{self.gemini_model}:"
                    f"generateContent?key={self.gemini_api_key}"
                )

                full_prompt = f"{system_msg}\n\n{prompt}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": full_prompt,
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "maxOutputTokens": max_output_tokens,
                    },
                }

                async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as http_client:
                    gemini_resp = await http_client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                    if gemini_resp.status_code >= 400:
                        try:
                            err_json = gemini_resp.json()
                            err_msg = err_json.get("error", {}).get("message", gemini_resp.text)
                        except Exception:
                            err_msg = gemini_resp.text
                        logger.warning(
                            "Gemini API HTTP %d Error (%s): %s",
                            gemini_resp.status_code,
                            "Quota/Rate Limit Exceeded" if gemini_resp.status_code == 429 else "Provider Error",
                            err_msg,
                        )
                        raise RuntimeError(
                            f"Gemini API HTTP {gemini_resp.status_code}: {err_msg}"
                        )

                    response_data = gemini_resp.json()

                    candidates = response_data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("Gemini returned no candidates.")

                    answer_text = (
                        candidates[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text")
                    )

                    if not answer_text:
                        raise RuntimeError("Gemini returned an empty response.")

                    return {
                        "answer": answer_text,
                        "confidence": "high",
                        "citations": citations,
                        "provider": f"Gemini ({self.gemini_model})",
                    }

            except httpx.TimeoutException as timeout_err:
                logger.warning(
                    "Gemini API Fallback Timeout (%s): request timed out after %.1fs",
                    type(timeout_err).__name__,
                    float(GEMINI_TIMEOUT.read or 20.0),
                )
            except Exception as error:
                logger.warning(
                    "Gemini API Fallback Error (%s): %s",
                    type(error).__name__,
                    error or repr(error),
                )

        return {
            "answer": (
                "AI reasoning services are currently unreachable. "
                "Please verify your NVIDIA NIM / Gemini API key "
                "configuration and network connection."
            ),
            "confidence": "none",
            "citations": [],
            "provider": "None",
        }

    async def stream_rag_response(
        self,
        question: str,
        contexts: List[Dict[str, Any]],
        repo_meta: Dict[str, Any] = None,
    ):
        import json

        if not contexts:
            no_ctx_msg = "No matching source code context found in this repository."
            yield {"type": "token", "text": no_ctx_msg}
            yield {
                "type": "done",
                "answer": no_ctx_msg,
                "citations": [],
                "provider": "None",
            }
            return

        system_msg, prompt, citations, max_output_tokens = self._prepare_rag_prompt(
            question, contexts, repo_meta
        )

        accumulated_answer = ""
        provider_used = None

        # 1. Primary provider: NVIDIA NIM Streaming
        if (
            self.nim_api_key
            and self.nim_api_key.startswith("nvapi-")
        ):
            try:
                nim_url = f"{self.nim_base_url.rstrip('/')}/chat/completions"
                nim_headers = {
                    "Authorization": f"Bearer {self.nim_api_key}",
                    "Content-Type": "application/json",
                }
                nim_payload = {
                    "model": self.nim_model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "top_p": 0.7,
                    "max_tokens": max_output_tokens,
                    "stream": True,
                }

                async with httpx.AsyncClient(timeout=NIM_TIMEOUT) as client:
                    async with client.stream(
                        "POST", nim_url, json=nim_payload, headers=nim_headers
                    ) as resp:
                        if resp.status_code >= 400:
                            err_body = await resp.aread()
                            err_text = err_body.decode('utf-8', errors='ignore')
                            logger.warning(
                                "NVIDIA NIM Stream HTTP %d Error: %s (falling back to Gemini)",
                                resp.status_code,
                                err_text,
                            )
                            raise RuntimeError(
                                f"NVIDIA NIM HTTP {resp.status_code}: {err_text}"
                            )

                        async for raw_line in resp.aiter_lines():
                            line = raw_line.strip()
                            if not line or not line.startswith("data:"):
                                continue
                            payload_str = line[5:].strip()
                            if payload_str == "[DONE]":
                                break
                            try:
                                data = json.loads(payload_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {}).get("content", "")
                                    if delta:
                                        accumulated_answer += delta
                                        yield {"type": "token", "text": delta}
                            except json.JSONDecodeError:
                                continue

                if accumulated_answer:
                    provider_used = f"NVIDIA NIM ({self.nim_model})"
                    yield {
                        "type": "done",
                        "answer": accumulated_answer,
                        "citations": citations,
                        "provider": provider_used,
                    }
                    return

            except httpx.TimeoutException as timeout_err:
                logger.warning(
                    "NVIDIA NIM Stream Timeout (%s): request timed out after %.1fs (falling back to Gemini)",
                    type(timeout_err).__name__,
                    float(NIM_TIMEOUT.read or 10.0),
                )
                accumulated_answer = ""
            except Exception as error:
                logger.warning(
                    "NVIDIA NIM Stream Error (%s) (falling back to Gemini): %s",
                    type(error).__name__,
                    error or repr(error),
                )
                accumulated_answer = ""

        # 2. Fallback provider: Google Gemini
        if (
            self.gemini_api_key
            and len(self.gemini_api_key) > 5
            and not self.gemini_api_key.startswith("your_")
        ):
            try:
                url = (
                    "https://generativelanguage.googleapis.com/"
                    f"v1beta/models/{self.gemini_model}:"
                    f"generateContent?key={self.gemini_api_key}"
                )

                full_prompt = f"{system_msg}\n\n{prompt}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": full_prompt,
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "maxOutputTokens": max_output_tokens,
                    },
                }

                async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as http_client:
                    gemini_resp = await http_client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                    if gemini_resp.status_code >= 400:
                        try:
                            err_json = gemini_resp.json()
                            err_msg = err_json.get("error", {}).get("message", gemini_resp.text)
                        except Exception:
                            err_msg = gemini_resp.text
                        logger.warning(
                            "Gemini API HTTP %d Error (%s): %s",
                            gemini_resp.status_code,
                            "Quota/Rate Limit Exceeded" if gemini_resp.status_code == 429 else "Provider Error",
                            err_msg,
                        )
                        raise RuntimeError(
                            f"Gemini API HTTP {gemini_resp.status_code}: {err_msg}"
                        )

                    response_data = gemini_resp.json()

                    candidates = response_data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("Gemini returned no candidates.")

                    answer_text = (
                        candidates[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text")
                    )

                    if not answer_text:
                        raise RuntimeError("Gemini returned an empty response.")

                    yield {"type": "token", "text": answer_text}
                    yield {
                        "type": "done",
                        "answer": answer_text,
                        "citations": citations,
                        "provider": f"Gemini ({self.gemini_model})",
                    }
                    return

            except httpx.TimeoutException as timeout_err:
                logger.warning(
                    "Gemini API Stream Fallback Timeout (%s): request timed out after %.1fs",
                    type(timeout_err).__name__,
                    float(GEMINI_TIMEOUT.read or 20.0),
                )
            except Exception as error:
                logger.warning(
                    "Gemini API Stream Fallback Error (%s): %s",
                    type(error).__name__,
                    error or repr(error),
                )

        # 3. Unreachable
        err_msg = (
            "AI reasoning services are currently unreachable. "
            "Please verify your NVIDIA NIM / Gemini API key "
            "configuration and network connection."
        )
        yield {"type": "token", "text": err_msg}
        yield {
            "type": "done",
            "answer": err_msg,
            "citations": [],
            "provider": "None",
        }