import os
import re
import urllib.request
import json
from typing import List, Dict, Any
from app.config import settings

class LLMService:
    def __init__(self):
        pass

    @property
    def nim_api_key(self) -> str:
        return os.getenv("NVIDIA_NIM_API_KEY") or getattr(settings, "NVIDIA_NIM_API_KEY", "")

    @property
    def nim_base_url(self) -> str:
        return os.getenv("NVIDIA_NIM_BASE_URL") or getattr(settings, "NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

    @property
    def nim_model(self) -> str:
        return os.getenv("NVIDIA_NIM_CHAT_MODEL") or getattr(settings, "NVIDIA_NIM_CHAT_MODEL", "meta/llama-3.1-70b-instruct")

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")

    @property
    def gemini_model(self) -> str:
        return os.getenv("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash")

    async def generate_rag_response(
        self, 
        question: str, 
        contexts: List[Dict[str, Any]],
        repo_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        if not contexts:
            return {
                "answer": "No matching source code context found in this repository.",
                "confidence": "low",
                "citations": []
            }

        context_string = ""
        citations = []
        for context_index, context_item in enumerate(contexts):
            context_string += f"\n--- Reference [{context_index + 1}]: {context_item['file_path']} (Lines {context_item['start_line']}-{context_item['end_line']}) ---\n"
            symbol_signature = context_item.get('signature', f"file {context_item['file_path']}")
            context_string += f"Symbol: {context_item['name']}\nSignature: {symbol_signature}\n"
            context_string += f"Code:\n{context_item['source_code']}\n"

            citations.append({
                "id": f"cite-{context_index + 1}",
                "label": f"{context_item['file_path'].split('/')[-1]}:{context_item['start_line']}-{context_item['end_line']}",
                "filePath": context_item["file_path"],
                "startLine": context_item["start_line"],
                "endLine": context_item["end_line"],
                "symbol": context_item["name"]
            })

        repo_name = repo_meta.get("name", "Workspace") if repo_meta else "Workspace"
        language = repo_meta.get("language", "Multi-Language") if repo_meta else "Multi-Language"
        all_files = repo_meta.get("all_files", []) if repo_meta else []

        word_limit_match = re.search(r'(?:under|in|within|max|less than|around)\s+(\d+)\s+words', question, re.IGNORECASE)
        max_words = int(word_limit_match.group(1)) if word_limit_match else None

        tree_limit = 10 if max_words else 30
        tree_overview = f"Workspace: {repo_name} ({language})\nIndexed File Tree ({len(all_files)} files):\n" + "\n".join([f"- {f}" for f in all_files[:tree_limit]])

        # Filter tree overview if query is specific to a target day/file to prevent model from comparing unasked days
        day_filter_match = re.search(r'day\s*(\d+)', question, re.IGNORECASE)
        if day_filter_match:
            target_day_number = day_filter_match.group(1)
            day_matching_files = [f for f in all_files if f"day{target_day_number}" in f.lower() or f"day_{target_day_number}" in f.lower() or f"day {target_day_number}" in f.lower()]
            if day_matching_files:
                tree_overview = f"Workspace: {repo_name} ({language})\nRelevant Target Files:\n" + "\n".join([f"- {f}" for f in day_matching_files])

        limit_instruction = ""
        max_output_tokens = 1024
        chosen_model = self.nim_model

        if max_words:
            limit_instruction = f"\n\nCRITICAL MANDATE: The user explicitly requested an answer in UNDER {max_words} WORDS. Keep your output STRICTLY under {max_words} words. Do NOT use multi-section headers or filler. Be concise."
            max_output_tokens = min(512, max(60, int(max_words * 2.5)))

        prompt = (
            f"You are an AI Codebase Knowledge Assistant.\n"
            f"Question: {question}\n\n"
            f"{tree_overview}\n\n"
            f"Retrieved Source Code Contexts:\n{context_string}\n\n"
            f"STRICT MANDATE:\n"
            f"1. State facts with 100% confidence based strictly on the provided source code.\n"
            f"2. ABSOLUTELY FORBIDDEN WORDS: 'likely', 'probably', 'may involve', 'most likely', 'seems to', 'depends on implementation'. Do NOT speculate.\n"
            f"3. Only reference files, routes, and functions that explicitly exist in the retrieved code contexts. If a file in context does not handle the query, ignore it completely instead of guessing.{limit_instruction}"
        )
        system_msg = (
            "You are a precise, authoritative codebase assistant. State exact facts based strictly on provided source code. "
            "NEVER use speculative or hedging words like 'likely', 'probably', 'may involve', 'most likely', 'depends on implementation', or 'not shown in code'. "
            "Cite exact file paths, routes, function names, and models with absolute certainty."
        )

        # 1. Primary: NVIDIA NIM API (Llama 3.1 70B Instruct)
        if self.nim_api_key and self.nim_api_key.startswith("nvapi-"):
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=self.nim_api_key,
                    base_url=self.nim_base_url,
                    timeout=60.0,
                    max_retries=2
                )
                response = await client.chat.completions.create(
                    model=chosen_model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=max_output_tokens
                )
                answer_content = response.choices[0].message.content
                return {
                    "answer": answer_content,
                    "confidence": "high",
                    "citations": citations
                }
            except Exception as error:
                print(f"NVIDIA NIM API Error (falling back to Gemini): {error}")

        # 2. Fallback 1: Gemini API
        if self.gemini_api_key and len(self.gemini_api_key) > 5 and not self.gemini_api_key.startswith("your_"):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
                full_prompt = f"{system_msg}\n\n{prompt}"
                payload = json.dumps({
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "topP": 0.7,
                        "maxOutputTokens": max_output_tokens
                    }
                }).encode("utf-8")

                gemini_request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(gemini_request, timeout=15) as gemini_response:
                    response_data = json.loads(gemini_response.read().decode("utf-8"))
                    answer_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                    return {
                        "answer": answer_text,
                        "confidence": "high",
                        "citations": citations
                    }
            except Exception as error:
                print(f"Gemini API Fallback Error: {error}")

        # 3. If BOTH unreachable: Return clear connection error
        return {
            "answer": "AI reasoning services are currently unreachable. Please verify your NVIDIA NIM / Gemini API key configuration and network connection.",
            "confidence": "none",
            "citations": []
        }

