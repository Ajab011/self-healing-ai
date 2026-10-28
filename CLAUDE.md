# Project: Self-Healing AI Automation System
## Code-E-Fiesta 2026 — Medicaps University × SlowBros Labs — Problem Statement 04

---

## 1. The Problem Statement (official)

**Track:** AI Engineering / Intelligent Monitoring
**Title:** The Self-Healing AI Automation System
**Tagline:** Autonomous error detection, root-cause diagnosis, and automated patch execution for mission-critical workflows.

**The problem:**
- Modern businesses depend on automated workflows and software integrations.
- When an API fails, data arrives in an unexpected format, or a workflow breaks, the entire process can stop.
- Identifying the cause and fixing the issue often requires manual, tedious intervention by engineers.
- Pain point: inefficiency, lack of personalization, and high manual operational overhead.

**The challenge:**
Build an AI-powered system that monitors workflows, detects failures, identifies their likely causes, and proposes or executes corrective actions.

**The solution should aim to:**
- Monitor a workflow and detect errors or unexpected outcomes.
- Analyze logs or execution data to identify the likely cause.
- Recommend or generate a corrective action.
- Validate the proposed fix and retry the failed process, with human approval where necessary.

**The bigger vision:**
What if business automations could detect problems, recover from failures, and maintain themselves with minimal human intervention?

---

## 2. Hackathon Rules

- 6-hour build sprint, single team, ONE problem statement only.
- Strict clock — commits after the buzzer are not evaluated.
- A working MVP is required — a static UI/slides alone does not qualify for prizes.
- Full stack freedom: any AI models, APIs, automation platforms, databases, open-source tools.

---

## 3. Judging Rubric (design every decision around this)

| Criterion | Weight | What it means for us |
|---|---|---|
| Technical execution & working MVP | 25% | The detect→diagnose→fix→retry loop must actually run live, not be faked/pre-recorded. Build this first, polish later. |
| Problem understanding & relevance | 20% | Use realistic failure types (schema drift, rate limits, bad data) and be able to explain the real pain point clearly in the pitch. |
| Innovation & originality | 20% | Real LLM reasoning over the error (not hardcoded if/else), confidence-based autonomy, live/freeform fault handling. |
| Practicality & real-world impact | 15% | Tie it to real tools (Zapier, n8n, PagerDuty-style monitoring) and state concrete time saved. |
| Use of AI & technology | 10% | One strong, meaningful LLM call that does real diagnosis + structured fix generation is enough — don't over-engineer this part. |
| Demo & clarity | 10% | Rehearsed, clear live demo + confident Q&A answers (e.g. "what if the fix is wrong?" → human approval checkpoint). |

**Priority rule:** get the ugly-but-working end-to-end loop solid before touching UI polish or extra features.

---

## 4. Tech Stack (fixed — do not deviate without updating this file)

| Layer | Tool | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Backend framework | FastAPI | latest (0.115+) |
| Server | Uvicorn | latest |
| AI SDK | `google-generativeai` (Gemini Python SDK, free tier) | latest — model set by `GEMINI_MODEL` in `.env`, default `gemini-3.5-flash`, fallback `gemini-3.5-flash-lite` (1.5 / 2.5 flash are retired for new keys; 3.8 times out on free tier) |
| Env vars | `python-dotenv` | latest |
| Frontend | Plain HTML5 + vanilla JS | — |
| CSS | Tailwind via CDN script tag | `cdn.tailwindcss.com` (no install step) |
| Data storage | Python in-memory dict/list | no DB needed for demo |
| API key | Gemini API key | from aistudio.google.com (free, no card), stored in `.env` as `GEMINI_API_KEY` |

No npm, no React, no database, no Docker, no build step. Every extra tool is one more thing that can break mid-hackathon.

---

## 5. File Structure

```
self-healing-ai/
├── backend/
│   ├── main.py              # FastAPI app, all routes
│   ├── healer.py            # Core logic: diagnose + fix via Claude API
│   ├── fault_injector.py    # Generates fake broken payloads
│   ├── requirements.txt
│   └── .env                 # holds GEMINI_API_KEY (never commit this)
├── frontend/
│   └── index.html           # Single-file dashboard: chaos button + incident cards
├── README.md
└── CLAUDE.md                # this file
```

---

## 6. Build Order (follow in sequence, test each step before moving on)

**Step 1 — Scaffold**
Create the FastAPI project: `backend/` with `requirements.txt` (fastapi, uvicorn, google-generativeai, python-dotenv — plain `uvicorn`, not `[standard]`: pyyaml has no wheel for Python 3.15), `.env.example`, and a `main.py` with a hello-world endpoint. Create `frontend/index.html` as a blank Tailwind CDN page.
✅ Verify: `pip install -r requirements.txt` then `uvicorn main:app --reload` responds on `localhost:8000`.

**Step 2 — Fault injector**
`backend/fault_injector.py`: function `get_random_fault()` returning one of 3 fake broken workflow payloads:
1. Schema drift (a field got renamed, e.g. `status` → `delivery_status`)
2. 429 rate-limit error
3. Malformed date/price field
Each returns a dict: `{payload, error, fault_type}`.

**Step 3 — The healer (core AI logic)**
`backend/healer.py`: function `diagnose_and_fix(payload, error)` that calls the Gemini API (`GEMINI_MODEL`, with `response_mime_type: "application/json"`) with a prompt describing the broken payload + error, asking for structured JSON back: `{cause, fix_type, fixed_payload, confidence}`.
✅ Verify: test this standalone with one fake error via a quick script before wiring into the API — protects the core loop.

**Step 4 — Wire the API**
`backend/main.py` endpoints:
- `POST /inject-fault` → calls fault_injector, stores new incident with status `"broken"`, returns incident id
- `GET /incidents` → returns all incidents
- `POST /incidents/{id}/heal` → runs healer.py on that incident, updates status to `"fixed"` or `"needs-approval"` based on confidence threshold

**Step 5 — Dashboard**
`frontend/index.html`: a big red "BREAK IT" button (calls `/inject-fault` then `/heal`), plus a list of incident cards that poll `GET /incidents` every 1.5s and render status as red/yellow/green with cause + fix shown.

**Step 6 — Polish (only if time remains)**
- Text input to paste a custom/freeform error and diagnose it live (judges can test this themselves)
- Short auto-generated incident summary after each fix
- Confidence-based color coding (green = auto-fixed, yellow = fixed but flagged, red = needs human approval)
- "Chaos button" that randomly triggers cascading failures

---

## 7. Stretch Ideas (only after core loop is rock solid)

- Freeform live diagnosis: let a judge type any garbage error and watch it get diagnosed in real time.
- Cascading failures: break 3 dependent things in sequence, show the system untangling all of them.
- Narration: system explains its reasoning in plain English as it works, not silent JSON logs.
- "Memory": if the same fault type repeats, instantly apply the known fix instead of re-diagnosing (simple lookup table, no real ML needed).
- Auto-generated incident postmortem after each fix.

---

## 8. Demo Script (prep in last 30 min)

1. "Here's a workflow. Watch it break." → press BREAK IT
2. "Watch the agent diagnose it." → show reasoning/cause on screen
3. "Watch it fix itself and retry." → status goes green
4. "Here's why this matters for a real business." → tie to time saved / real tools (Zapier, n8n, PagerDuty)
5. Be ready for: "What if the fix is wrong?" → answer: low-confidence fixes pause for human approval, never auto-applied blind.
