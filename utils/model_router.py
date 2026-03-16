import json
import os
import re
import time
from urllib import error, request

from dotenv import load_dotenv

# Load environment variables from .env once at import time.
load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
BEDROCK_OPENAI_API_URL = os.getenv(
    "AWS_BEDROCK_OPENAI_API_URL",
    "https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1/chat/completions"
)

# Use OpenRouter as primary provider. Allow per-role model overrides.
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.7-sonnet")
OPENROUTER_PLANNER_MODEL = os.getenv("OPENROUTER_PLANNER_MODEL", DEFAULT_OPENROUTER_MODEL)
OPENROUTER_CODER_MODEL = os.getenv("OPENROUTER_CODER_MODEL", DEFAULT_OPENROUTER_MODEL)
OPENROUTER_DEBUGGER_MODEL = os.getenv("OPENROUTER_DEBUGGER_MODEL", DEFAULT_OPENROUTER_MODEL)
GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "4"))
BEDROCK_MAX_TOKENS = int(os.getenv("BEDROCK_MAX_TOKENS", os.getenv("OPENROUTER_MAX_TOKENS", "1024")))

# Bedrock / Nova role-based model mapping
DEFAULT_BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "amazon.nova-pro-v1:0")
BEDROCK_PLANNER_MODEL = os.getenv("BEDROCK_PLANNER_MODEL", DEFAULT_BEDROCK_MODEL)
BEDROCK_CODER_MODEL = os.getenv("BEDROCK_CODER_MODEL", DEFAULT_BEDROCK_MODEL)
BEDROCK_DEBUGGER_MODEL = os.getenv("BEDROCK_DEBUGGER_MODEL", DEFAULT_BEDROCK_MODEL)


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


def _get_bedrock_bearer_token():
    return os.getenv("AWS_BEARER_TOKEN_BEDROCK", "").strip()


def _get_openrouter_max_tokens():
    raw = os.getenv("OPENROUTER_MAX_TOKENS", "96").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 96

    if parsed <= 0:
        parsed = 96

    # Keep OpenRouter requests affordable by default in hosted environments.
    return min(parsed, 96)


def _bedrock_chat(system_prompt, user_prompt, model):
    token = _get_bedrock_bearer_token()
    if not token:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is not set")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0,
        "max_tokens": BEDROCK_MAX_TOKENS,
    }

    req = request.Request(
        BEDROCK_OPENAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Bedrock request failed: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Bedrock connection failed: {exc.reason}") from exc

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("Bedrock returned no choices")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError("Bedrock returned empty content")

    return content


def _openrouter_chat_with_key(system_prompt, user_prompt, model, api_key):

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0,
        "max_tokens": _get_openrouter_max_tokens()
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

    try:
        client = Groq(api_key=api_key)
    except TypeError as exc:
        message = str(exc)
        if "proxies" in message:
            raise RuntimeError(
                "Groq client initialization failed due to an httpx compatibility issue "
                "(unexpected keyword argument 'proxies'). Pin httpx to a compatible version "
                "or force a different provider with LLM_PROVIDER=openrouter."
            ) from exc
        raise RuntimeError(f"Groq client initialization failed: {message}") from exc
    except Exception as exc:
        raise RuntimeError(f"Groq client initialization failed: {exc}") from exc

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


def _chat_with_fallback(system_prompt, user_prompt, bedrock_model, openrouter_model, groq_model):
    provider_errors = []

    # Optional strict provider selection: bedrock, openrouter, groq, auto
    provider_mode = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    if provider_mode not in {"auto", "bedrock", "openrouter", "groq"}:
        provider_mode = "auto"

    has_bedrock = bool(_get_bedrock_bearer_token())
    has_openrouter = bool(_get_openrouter_api_keys())
    has_groq = bool(os.getenv("GROQ_API_KEY"))

    if provider_mode == "bedrock":
        if not has_bedrock:
            raise RuntimeError("LLM_PROVIDER=bedrock but AWS_BEARER_TOKEN_BEDROCK is not set")
        return _bedrock_chat(system_prompt, user_prompt, bedrock_model)

    if provider_mode == "openrouter":
        if not has_openrouter:
            raise RuntimeError("LLM_PROVIDER=openrouter but OPENROUTER_API_KEY/OPENROUTER_API_KEYS is not set")
        return _openrouter_chat(system_prompt, user_prompt, openrouter_model)

    if provider_mode == "groq":
        if not has_groq:
            raise RuntimeError("LLM_PROVIDER=groq but GROQ_API_KEY is not set")
        return _groq_chat(system_prompt, user_prompt, groq_model)

    if not (has_bedrock or has_openrouter or has_groq):
        raise RuntimeError(
            "No LLM provider credentials found. Set at least one of: "
            "AWS_BEARER_TOKEN_BEDROCK, OPENROUTER_API_KEY/OPENROUTER_API_KEYS, or GROQ_API_KEY"
        )

    if has_bedrock:
        try:
            return _bedrock_chat(system_prompt, user_prompt, bedrock_model)
        except RuntimeError as exc:
            provider_errors.append(f"bedrock: {exc}")

    if has_openrouter:
        try:
            return _openrouter_chat(system_prompt, user_prompt, openrouter_model)
        except RuntimeError as exc:
            provider_errors.append(f"openrouter: {exc}")

    if has_groq:
        try:
            return _groq_chat(system_prompt, user_prompt, groq_model)
        except RuntimeError as exc:
            provider_errors.append(f"groq: {exc}")

    raise RuntimeError("All configured LLM providers failed: " + " | ".join(provider_errors))


def planner_model(prompt):
    return _chat_with_fallback(
        system_prompt="You are a senior software architect.",
        user_prompt=prompt,
        bedrock_model=BEDROCK_PLANNER_MODEL,
        openrouter_model=OPENROUTER_PLANNER_MODEL,
        groq_model="llama-3.3-70b-versatile"
    )


def coder_model(prompt):
    return _chat_with_fallback(
        system_prompt="You are an expert Python developer.",
        user_prompt=prompt,
        bedrock_model=BEDROCK_CODER_MODEL,
        openrouter_model=OPENROUTER_CODER_MODEL,
        groq_model="llama-3.1-8b-instant"
    )


def debugger_model(prompt):
    return _chat_with_fallback(
        system_prompt="You are a senior debugging engineer.",
        user_prompt=prompt,
        bedrock_model=BEDROCK_DEBUGGER_MODEL,
        openrouter_model=OPENROUTER_DEBUGGER_MODEL,
        groq_model="llama-3.1-8b-instant"
    )