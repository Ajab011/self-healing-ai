import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv()

from fault_injector import EXPECTED_SCHEMA, get_random_fault  # noqa: E402
from healer import diagnose_and_fix  # noqa: E402

app = FastAPI(title="Self-Healing AI Automation System")

# Frontend is opened as a plain file / different port, so allow all origins for the demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
CONFIDENCE_THRESHOLD = 0.85  # below this, a fix waits for human approval
MAX_BACKOFF_SECONDS = 3  # cap real Retry-After waits so the demo stays snappy
VALID_STATUSES = {"pending", "shipped", "delivered", "cancelled"}
ISO_8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

incidents: dict[int, dict] = {}
_lock = threading.Lock()
_next_id = 1


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _log(incident: dict, message: str) -> None:
    incident["timeline"].append({"time": _now(), "message": message})


def _validate(payload: dict) -> list[str]:
    """Simulated downstream CRM: returns a list of problems (empty = accepted)."""
    problems = [f"missing field '{key}'" for key in EXPECTED_SCHEMA if key not in payload]
    problems += [f"unexpected field '{key}'" for key in payload if key not in EXPECTED_SCHEMA]
    if "status" in payload and payload["status"] not in VALID_STATUSES:
        problems.append(f"invalid status '{payload['status']}'")
    if "total_price" in payload and not isinstance(payload["total_price"], (int, float)):
        problems.append("total_price is not a number")
    if "created_at" in payload and not ISO_8601.match(str(payload["created_at"])):
        problems.append("created_at is not ISO 8601")
    return problems


def _run_healer(incident_id: int) -> None:
    incident = incidents[incident_id]
    started = time.time()
    result = diagnose_and_fix(incident["payload"], incident["error"], incident["workflow"], EXPECTED_SCHEMA)
    incident["diagnosis"] = result
    _log(incident, f"Diagnosis: {result['cause']}")
    _log(incident, f"Proposed fix: {result['fix_type']} (confidence {result['confidence']:.0%})")

    if result["fix_type"] == "manual_review" or result["confidence"] < CONFIDENCE_THRESHOLD:
        incident["status"] = "needs-approval"
        _log(incident, "Confidence below threshold - paused for human approval")
    else:
        _retry(incident)
    incident["heal_seconds"] = round(time.time() - started, 1)


def _retry(incident: dict) -> None:
    fix = incident["diagnosis"]
    if fix["fix_type"] == "retry_with_backoff":
        match = re.search(r"Retry-After:\s*(\d+)", incident["error"])
        wait = min(int(match.group(1)) if match else 1, MAX_BACKOFF_SECONDS)
        _log(incident, f"Backing off {wait}s before retry")
        incident["status"] = "retrying"
        time.sleep(wait)

    problems = _validate(fix["fixed_payload"])
    if problems:
        incident["status"] = "needs-approval"
        _log(incident, f"Retry rejected by validation: {', '.join(problems)}")
    else:
        incident["status"] = "fixed"
        _log(incident, "Retried POST /v2/orders -> 200 OK. Workflow resumed.")


@app.get("/")
def dashboard():
    return FileResponse(FRONTEND)


@app.get("/health")
def health():
    return {"status": "ok", "message": "Self-Healing AI backend is running"}


@app.post("/inject-fault")
def inject_fault():
    global _next_id
    fault = get_random_fault()
    with _lock:
        incident_id = _next_id
        _next_id += 1
    incident = {
        "id": incident_id,
        "status": "broken",
        "fault_type": fault["fault_type"],
        "workflow": fault["workflow"],
        "payload": fault["payload"],
        "error": fault["error"],
        "diagnosis": None,
        "created_at": _now(),
        "heal_seconds": None,
        "timeline": [],
    }
    _log(incident, f"Workflow step failed: {fault['error']}")
    incidents[incident_id] = incident
    return {"id": incident_id}


@app.get("/incidents")
def list_incidents():
    return sorted(incidents.values(), key=lambda i: i["id"], reverse=True)


@app.post("/incidents/{incident_id}/heal")
def heal(incident_id: int, background_tasks: BackgroundTasks):
    incident = incidents.get(incident_id)
    if incident is None:
        raise HTTPException(404, "Incident not found")
    if incident["status"] != "broken":
        return {"id": incident_id, "status": incident["status"]}
    incident["status"] = "diagnosing"
    _log(incident, "AI healer diagnosing...")
    # Runs after the response so the dashboard can show "diagnosing" while Gemini thinks.
    background_tasks.add_task(_run_healer, incident_id)
    return {"id": incident_id, "status": "diagnosing"}


@app.post("/incidents/{incident_id}/approve")
def approve(incident_id: int, background_tasks: BackgroundTasks):
    incident = incidents.get(incident_id)
    if incident is None:
        raise HTTPException(404, "Incident not found")
    if incident["status"] != "needs-approval" or not incident["diagnosis"]:
        raise HTTPException(409, "Incident is not awaiting approval")
    _log(incident, "Fix approved by human operator")
    incident["status"] = "retrying"
    background_tasks.add_task(_retry, incident)
    return {"id": incident_id, "status": "retrying"}
