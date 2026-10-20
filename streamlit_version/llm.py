"""LLM 호출 모듈: groq를 먼저 쓰고, 실패하면 gemini로 자동 전환한다."""
import os

import httpx
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def _call_groq(messages: list[dict]) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    res = client.chat.completions.create(
        model=GROQ_MODEL, messages=messages, temperature=0.7
    )
    return res.choices[0].message.content


def _call_gemini(messages: list[dict]) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 .env에 없습니다.")
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in messages
        if m["role"] != "system"
    ]
    body = {"contents": contents}
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    res = httpx.post(url, json=body, headers={"x-goog-api-key": key}, timeout=60)
    res.raise_for_status()
    return res.json()["candidates"][0]["content"]["parts"][0]["text"]


def chat(messages: list[dict]) -> tuple[str, str]:
    """(답변, 사용한 공급자)를 반환한다. groq 실패 시 gemini로 폴백."""
    try:
        return _call_groq(messages), "groq"
    except Exception as groq_err:
        try:
            return _call_gemini(messages), "gemini"
        except Exception as gemini_err:
            raise RuntimeError(
                f"groq 실패: {groq_err}\ngemini 실패: {gemini_err}"
            ) from gemini_err
