"""Core AI logic: ask Gemini to diagnose a failed workflow step and generate a fix.

diagnose_and_fix(payload, error) -> {cause, fix_type, fixed_payload, confidence}
"""

import json
import os
import time
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)  # SDK deprecation notice, not useful mid-demo
    import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core import exceptions, retry

load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT", "30"))
FIX_TYPES = ["rename_field", "transform_data", "retry_with_backoff", "manual_review"]

# The SDK silently retries 503/504 for up to 10 minutes; disable that so we fail fast.
_REQUEST_OPTIONS = {"timeout": TIMEOUT_SECONDS, "retry": retry.Retry(predicate=lambda exc: False)}

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set - add it to backend/.env")
genai.configure(api_key=API_KEY)

# Free-tier models 503 under load, so retry briefly and alternate with a fallback model.
FALLBACK_MODEL_NAME = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
MAX_ATTEMPTS = 3
_TRANSIENT = (exceptions.ServiceUnavailable, exceptions.ResourceExhausted, exceptions.DeadlineExceeded)
_GENERATION_CONFIG = {"response_mime_type": "application/json", "temperature": 0.2}
_models = [genai.GenerativeModel(name, generation_config=_GENERATION_CONFIG) for name in (MODEL_NAME, FALLBACK_MODEL_NAME)]


def _generate(prompt: str) -> str:
    for attempt in range(MAX_ATTEMPTS):
        try:
            return _models[attempt % 2].generate_content(prompt, request_options=_REQUEST_OPTIONS).text
        except _TRANSIENT:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(attempt + 1)

PROMPT = """You are an SRE agent that repairs failed steps in business automation workflows
(think Zapier / n8n). A workflow step failed. Diagnose the root cause and produce a fix.

Workflow: {workflow}
Expected schema of the downstream API:
{expected_schema}

Failed payload:
{payload}

Error returned:
{error}

Respond with ONLY a JSON object with exactly these keys:
- "cause": one or two plain-English sentences explaining the root cause.
- "fix_type": one of {fix_types}.
    rename_field = upstream renamed/moved fields; map them back.
    transform_data = values are in the wrong format/type; convert them.
    retry_with_backoff = payload is fine, the failure is transient (rate limit, timeout); resend as-is after waiting.
    manual_review = you cannot fix this safely.
- "fixed_payload": the corrected payload that should be retried (the original unchanged for retry_with_backoff).
    Never invent data that is not derivable from the original payload.
- "confidence": a number from 0 to 1 for how sure you are the fix is correct and safe to auto-apply.
"""


def diagnose_and_fix(payload: dict, error: str, workflow: str = "unknown", expected_schema: dict | None = None) -> dict:
    prompt = PROMPT.format(
        workflow=workflow,
        expected_schema=json.dumps(expected_schema or "unknown", indent=2),
        payload=json.dumps(payload, indent=2, ensure_ascii=False),
        error=error,
        fix_types=FIX_TYPES,
    )
    try:
        result = json.loads(_generate(prompt))
    except Exception as exc:
        # Never crash the loop: an AI failure becomes a human-approval incident.
        return {
            "cause": f"Healer could not diagnose this automatically ({type(exc).__name__}: {exc})",
            "fix_type": "manual_review",
            "fixed_payload": payload,
            "confidence": 0.0,
        }

    try:
        confidence = min(max(float(result.get("confidence", 0)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.0
    fix_type = result.get("fix_type")
    return {
        "cause": str(result.get("cause", "No cause given")),
        "fix_type": fix_type if fix_type in FIX_TYPES else "manual_review",
        "fixed_payload": result.get("fixed_payload") if isinstance(result.get("fixed_payload"), dict) else payload,
        "confidence": confidence,
    }


if __name__ == "__main__":
    from fault_injector import get_random_fault

    fault = get_random_fault()
    print(f"Injected fault: {fault['fault_type']}")
    print(json.dumps(fault["payload"], indent=2, ensure_ascii=False))
    print(fault["error"], "\n")
    result = diagnose_and_fix(fault["payload"], fault["error"], fault["workflow"], fault["expected_schema"])
    print(f"Model: {MODEL_NAME}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
