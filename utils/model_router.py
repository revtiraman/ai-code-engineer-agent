import json
import os
import re
import time
from urllib import error, request

from dotenv import load_dotenv

# Load environment variables from .env once at import time.
load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Use OpenRouter as primary provider. Allow per-role model overrides.
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.7-sonnet")
OPENROUTER_PLANNER_MODEL = os.getenv("OPENROUTER_PLANNER_MODEL", DEFAULT_OPENROUTER_MODEL)
OPENROUTER_CODER_MODEL = os.getenv("OPENROUTER_CODER_MODEL", DEFAULT_OPENROUTER_MODEL)
OPENROUTER_DEBUGGER_MODEL = os.getenv("OPENROUTER_DEBUGGER_MODEL", DEFAULT_OPENROUTER_MODEL)
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "1024"))
GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "4"))


def _extract_retry_delay_seconds(message, default_delay=3.0):
    match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", message, flags=re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    return default_delay


def _get_openrouter_api_keys():
    keys = []

    multi_keys = os.getenv("OPENROUTER_API_KEYS", "")
    if multi_keys:
        keys.extend([k.strip() for k in multi_keys.split(",") if k.strip()])

    single_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if single_key and single_key not in keys:
        keys.append(single_key)

    return keys


def _openrouter_chat_with_key(system_prompt, user_prompt, model, api_key):

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0,
        "max_tokens": OPENROUTER_MAX_TOKENS
    }

    req = request.Request(
        OPENROUTER_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:3000"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "AI Engineer")
        },
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenRouter request failed: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"OpenRouter connection failed: {exc.reason}") from exc

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("OpenRouter returned no choices")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError("OpenRouter returned empty content")

    return content


def _openrouter_chat(system_prompt, user_prompt, model):
    api_keys = _get_openrouter_api_keys()
    if not api_keys:
        raise RuntimeError("OPENROUTER_API_KEY or OPENROUTER_API_KEYS is not set")

    errors = []
    for index, api_key in enumerate(api_keys, start=1):
        try:
            return _openrouter_chat_with_key(system_prompt, user_prompt, model, api_key)
        except RuntimeError as exc:
            errors.append(f"key#{index}: {exc}")

    raise RuntimeError("OpenRouter request failed for all keys: " + " | ".join(errors))


def _groq_chat(system_prompt, user_prompt, model):
    try:
        from groq import Groq
    except Exception as exc:
        raise RuntimeError("Groq SDK is not installed") from exc

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    client = Groq(api_key=api_key)

    last_error = None
    for attempt in range(1, GROQ_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0
            )
            return response.choices[0].message.content
        except Exception as exc:
            message = str(exc)
            last_error = message

            is_rate_limited = (
                "429" in message
                or "rate limit" in message.lower()
                or "rate_limit_exceeded" in message.lower()
            )

            if not is_rate_limited or attempt == GROQ_MAX_RETRIES:
                break

            # Respect provider hint when present, then add tiny jitter.
            delay = _extract_retry_delay_seconds(message) + 0.25
            time.sleep(delay)

    raise RuntimeError(f"Groq request failed: {last_error}")


def _chat_with_fallback(system_prompt, user_prompt, openrouter_model, groq_model):
    if _get_openrouter_api_keys():
        try:
            return _openrouter_chat(system_prompt, user_prompt, openrouter_model)
        except RuntimeError as exc:
            # If OpenRouter keys are exhausted/invalid, continue with Groq.
            if os.getenv("GROQ_API_KEY"):
                return _groq_chat(system_prompt, user_prompt, groq_model)
            raise exc

    return _groq_chat(system_prompt, user_prompt, groq_model)


def planner_model(prompt):
    return _chat_with_fallback(
        system_prompt="You are a senior software architect.",
        user_prompt=prompt,
        openrouter_model=OPENROUTER_PLANNER_MODEL,
        groq_model="llama-3.3-70b-versatile"
    )


def coder_model(prompt):
    return _chat_with_fallback(
        system_prompt="You are an expert Python developer.",
        user_prompt=prompt,
        openrouter_model=OPENROUTER_CODER_MODEL,
        groq_model="llama-3.1-8b-instant"
    )


def debugger_model(prompt):
    return _chat_with_fallback(
        system_prompt="You are a senior debugging engineer.",
        user_prompt=prompt,
        openrouter_model=OPENROUTER_DEBUGGER_MODEL,
        groq_model="llama-3.1-8b-instant"
    )