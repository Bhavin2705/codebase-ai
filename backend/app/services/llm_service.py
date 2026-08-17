import logging
import os
import re
from typing import Any, Dict, List
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        pass

    @property
    def nim_api_key(self) -> str:
        return os.getenv("NVIDIA_NIM_API_KEY") or getattr(
            settings, "NVIDIA_NIM_API_KEY", ""
        )

    @property
    def nim_base_url(self) -> str:
        return os.getenv("NVIDIA_NIM_BASE_URL") or getattr(
            settings,
            "NVIDIA_NIM_BASE_URL",
            "https://integrate.api.nvidia.com/v1",
        )

    @property
    def nim_model(self) -> str:
        return os.getenv("NVIDIA_NIM_CHAT_MODEL") or getattr(
            settings,
            "NVIDIA_NIM_CHAT_MODEL",
            "meta/llama-3.1-70b-instruct",
        )

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY") or getattr(
            settings, "GEMINI_API_KEY", ""
        )

    @property
    def gemini_model(self) -> str:
        return os.getenv("GEMINI_MODEL") or getattr(
            settings,
            "GEMINI_MODEL",
            "gemini-2.0-flash",
        )

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

        # ---------------------------------------------------------
        # Build retrieved source-code context and citations
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # Repository metadata
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # Detect requested word limit
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # Build repository tree overview
        # ---------------------------------------------------------
        tree_limit = 10 if max_words else 30

        tree_overview = (
            f"Workspace: {repo_name} ({language})\n"
            f"Indexed File Tree ({len(all_files)} files):\n"
            + "\n".join(
                f"- {file_path}"
                for file_path in all_files[:tree_limit]
            )
        )

        # ---------------------------------------------------------
        # If the question targets a specific day, restrict the
        # tree overview to matching files.
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # Output limits
        # ---------------------------------------------------------
        limit_instruction = ""
        max_output_tokens = 1024

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
                512,
                max(60, int(max_words * 2.5)),
            )

        # ---------------------------------------------------------
        # System instructions
        # ---------------------------------------------------------
        system_msg = (
            "You are a precise AI Codebase Knowledge Assistant. "
            "Your answers must be grounded exclusively in the source "
            "code and repository metadata provided in the current "
            "request.\n\n"

            "GROUNDING RULES:\n"
            "1. Treat the retrieved source-code context as the only "
            "authoritative evidence for implementation-specific claims.\n"
            "2. Do not invent files, routes, functions, classes, "
            "models, variables, database tables, APIs, or behavior.\n"
            "3. Only mention a file, route, function, class, model, "
            "or symbol when it exists in the provided context.\n"
            "4. Do not infer implementation details that are not "
            "supported by the provided code.\n"
            "5. If the provided context does not contain enough "
            "evidence to answer the question, explicitly state that "
            "the retrieved source context is insufficient and explain "
            "what cannot be established from it.\n"
            "6. Never present an inference as an established fact.\n"
            "7. Do not use external knowledge to fill gaps in the "
            "repository context.\n\n"

            "UNCERTAINTY RULES:\n"
            "Do not use speculative language such as 'likely', "
            "'probably', 'may involve', 'most likely', 'seems to', "
            "or 'depends on implementation'.\n"
            "When evidence is missing, say that the provided context "
            "does not establish the answer instead of guessing.\n\n"

            "CITATION RULES:\n"
            "When describing implementation details, cite the exact "
            "file path and relevant line range supplied in the "
            "retrieved context.\n"
            "Use exact function, class, route, and model names from "
            "the provided source code.\n\n"

            "ANSWERING RULES:\n"
            "Answer the user's actual question directly. "
            "Ignore retrieved files that are unrelated to the question. "
            "Do not describe unrelated repository components."
        )

        # ---------------------------------------------------------
        # User prompt containing repository evidence
        # ---------------------------------------------------------
        prompt = (
            "You are an AI Codebase Knowledge Assistant.\n\n"
            f"Question:\n{question}\n\n"
            f"{tree_overview}\n\n"
            "Retrieved Source Code Contexts:\n"
            f"{context_string}\n\n"
            "STRICT EVIDENCE MANDATE:\n"
            "1. Base implementation-specific claims only on the "
            "provided source-code contexts.\n"
            "2. Do not speculate or invent missing implementation "
            "details.\n"
            "3. Only reference files, routes, functions, classes, "
            "models, and symbols explicitly present in the retrieved "
            "contexts.\n"
            "4. If the retrieved context is insufficient, explicitly "
            "say so rather than guessing.\n"
            "5. Ignore retrieved files that do not provide evidence "
            "for the user's question."
            f"{limit_instruction}"
        )

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # ---------------------------------------------------------
            # 1. Primary provider: NVIDIA NIM (native HTTP POST)
            # ---------------------------------------------------------
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

                    nim_resp = await http_client.post(
                        nim_url,
                        json=nim_payload,
                        headers=nim_headers,
                    )

                    if nim_resp.status_code >= 400:
                        raise RuntimeError(
                            f"NVIDIA NIM HTTP {nim_resp.status_code}: {nim_resp.text}"
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

                except Exception as error:
                    logger.warning(
                        "NVIDIA NIM API Error (falling back to Gemini): %s",
                        error,
                    )

            # ---------------------------------------------------------
            # 2. Fallback provider: Google Gemini (native HTTP POST)
            # ---------------------------------------------------------
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
                            "temperature": 0.2,
                            "topP": 0.7,
                            "maxOutputTokens": max_output_tokens,
                        },
                    }

                    gemini_resp = await http_client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    response_data = gemini_resp.json()

                    if (
                        isinstance(getattr(gemini_resp, "status_code", None), int)
                        and gemini_resp.status_code >= 400
                    ):
                        err_msg = response_data.get("error", {}).get(
                            "message", getattr(gemini_resp, "text", "")
                        )
                        raise RuntimeError(
                            f"Gemini API HTTP {gemini_resp.status_code}: {err_msg}"
                        )

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

                except Exception as error:
                    logger.warning(
                        "Gemini API Fallback Error: %s",
                        error,
                    )

        # ---------------------------------------------------------
        # 3. Both providers unavailable
        # ---------------------------------------------------------
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