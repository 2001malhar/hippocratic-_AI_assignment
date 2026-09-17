# Bedtime Story Agent

Generates bedtime stories for children aged 5–10 using a **LangGraph** agent that plans,
writes, judges and revises the story until it clears a strict safety and bedtime-quality
bar — served over a **FastAPI** JSON API with a **Gradio** UI, from one process on one port.

The core idea: a single prompt cannot reliably produce a story that is simultaneously
on-request, age-appropriate, emotionally safe and *calming enough to fall asleep to*. So the
work is split into stages, and an LLM judge scores each draft against a rubric — but the
**judge never decides whether a story passes**. It supplies opinions; Python supplies the
verdict.

---

## The graph

```
START ──▶ plan_story ──▶ generate_story ──▶ judge ──▶ threshold_detector
                                             ▲                  │
                                             │   below bar      │  meets bar, or
                                             │                  │  revision budget spent
                                             └──── refine ◀──────┼──────▶ publish ──▶ END
```

| Node | Type | What it does |
|---|---|---|
| `plan_story` | **LLM** | Turns the request into a validated 8-field story plan (characters, setting, arc, lesson, bedtime ending) |
| `generate_story` | **LLM** | Writes the first 400–700 word draft from the plan |
| `judge` | **LLM** | Scores 6 rubric dimensions 1–5, checks 8 parental content flags, quotes the closing lines |
| `threshold_detector` | **Deterministic** | Applies the acceptance policy and routes: publish or refine |
| `refine` | **LLM** | Rewrites using the judge's feedback, then loops back to `judge` |
| `publish` | **Deterministic** | Finalises the best draft, splits off the title, emits it |

Four LLM steps, two pure-Python steps. The gate sits immediately after the **first** judge
pass, so a strong first draft publishes in 3 LLM calls rather than paying for a revision it
does not need. `refine` always re-enters `judge` — nothing is ever published unscored.

---

## Why the judge does not decide

The judge prompt explicitly says *"Do not calculate the overall score. Do not decide whether
the story passes."* It returns raw observations; [`app/services/evaluation.py`](app/services/evaluation.py)
turns them into a verdict. That module is pure — same input, same output, no network — which
is what makes the acceptance criteria auditable rather than a matter of model mood.

It applies three rules the model cannot argue with:

**1. Threshold gate.** Configurable minimums per metric. `story_quality` and `story_structure`
count toward the average but are *not* gated individually: a slightly plain story is
publishable, an unsafe or off-request one never is.

**2. Parental safety veto.** The judge reports 8 content flags (`violence`, `scary_imagery`,
`death_or_loss`, `cruelty`, `unresolved_distress`, `adult_themes`, `unsafe_behavior_modeled`,
`frightening_ending`). Any flag set forces `emotional_safety` down to ≤ 2 and fails the story
outright — regardless of the arithmetic. A model that flags `violence: true` and then awards
emotional safety 5/5 is not hypothetical, so the flag decides, not the score.

**3. Calming-ending check.** Before scoring `bedtime_quality`, the judge must copy the story's
final sentences verbatim into the response and rule on whether *those exact sentences* leave a
child settled. Forcing it to quote the ending is the cheapest reliable way to stop
`gpt-3.5-turbo` from rubber-stamping an abrupt one. A failed check caps `bedtime_quality` at 3
and sends a mandatory rewrite instruction to the reviser.

If the revision budget runs out, the graph publishes the **best-scoring draft it saw**, not
the last one — a revision sometimes fixes the flagged issue and regresses something else.

---

## Quick start

Requires **Python ≥ 3.10** (Gradio 5 and LangGraph). If `python --version` reports 3.9, use
the launcher to pick a newer one.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env      # then add your OPENAI_API_KEY

python main.py
```

| URL | |
|---|---|
| http://127.0.0.1:8000/ui | Gradio interface |
| http://127.0.0.1:8000/docs | OpenAPI / Swagger |
| http://127.0.0.1:8000/healthz | Liveness (makes no LLM call) |

### Command line

Runs interactively with no flags, or non-interactively with them:

```powershell
python cli.py                                                    # interactive prompts
python cli.py --request "A sleepy dragon loses his blanket" --style cozy
python cli.py --request "..." --debug                            # plan + full judge trace
python cli.py --request "..." --json                             # machine-readable
```

### API

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/stories `
  -H "Content-Type: application/json" `
  -d '{\"request\": \"A tiny fox helps a lost bunny\", \"style\": \"cozy\"}'
```

Returns the published story plus the plan, the score card, and a per-iteration judge trace —
so a caller can see exactly *why* the story was accepted, not just that it was.

---

## Project layout

```
main.py                        uvicorn entrypoint (API + UI)
cli.py                         command-line entrypoint
app/
├── application.py             FastAPI factory, lifespan, Gradio mount
├── settings.py                pydantic-settings; every threshold is env-tunable
├── styles.py                  the style catalogue, shared by API / UI / CLI
├── core/                      exceptions, run-id-aware logging
├── schemas/                   story.py (domain) + api.py (HTTP contracts)
├── prompts/                   planner / storyteller / judge / reviser
├── llm/                       role-configured clients + resilient JSON extraction
├── graph/
│   ├── state.py               StoryState
│   ├── builder.py             graph assembly
│   ├── routing.py             conditional edge
│   └── nodes/                 one module per node
├── services/
│   ├── evaluation.py          the deterministic policy (pure)
│   └── story_service.py       runs the graph; used by API, UI and CLI alike
├── api/                       routers, dependencies, error handlers
└── ui/                        Gradio Blocks
```

`StoryService` is the single entry point for all three interfaces, so the API, the UI and the
CLI cannot drift apart. The Gradio UI calls it **in-process** rather than looping back over
HTTP to its own server.

---

## Configuration

Every knob lives in `.env` (see `.env.example`). The ones that matter:

| Variable | Default | |
|---|---|---|
| `OPENAI_API_KEY` | — | Required |
| `LLM_MODEL` | `gpt-3.5-turbo` | Fixed for this project |
| `MAX_REVISIONS` | `2` | Refine passes before publishing the best draft |
| `THRESHOLD_OVERALL` | `4.0` | Minimum average |
| `THRESHOLD_REQUEST_ADHERENCE` | `4` | |
| `THRESHOLD_AGE_APPROPRIATENESS` | `4` | |
| `THRESHOLD_EMOTIONAL_SAFETY` | `4` | |
| `THRESHOLD_BEDTIME_QUALITY` | `4` | |

Thresholds are settings rather than constants specifically so the revision loop can be
demonstrated. `gpt-3.5-turbo` is a generous judge and usually passes a decent first draft, so
to watch the cycle actually run:

```powershell
$env:THRESHOLD_OVERALL="4.9"; $env:THRESHOLD_EMOTIONAL_SAFETY="5"
python cli.py --request "A tiny fox helps a lost bunny" --debug
```

The debug output then shows three judge passes, the feedback handed to each revision, and
which draft was published.

---

## Working with `gpt-3.5-turbo`

The model is fixed, and it predates structured outputs — it supports JSON *mode* but not
`json_schema`, so a well-formed object is guaranteed but a *correctly shaped* one is not.
Four layers handle that:

1. `response_format: {"type": "json_object"}` on planner and judge calls
2. Fence-stripping and brace-slicing in [`app/llm/json_utils.py`](app/llm/json_utils.py)
3. One retry with stricter output instructions
4. Pydantic validation at the node boundary

The planner gets a fifth: on a schema failure it is re-asked once with the specific validation
errors quoted back to it, which recovers most malformed plans. Score coercion fails *safe* — a
missing or non-numeric score is read as 1.0, never as a pass.

---

## Design notes

**LangGraph for the revision cycle.** The cycle is a state machine with a conditional edge,
and expressing it as one keeps the control flow inspectable: the routing decision and its
reason are written into state, so the trace shows not just what the pipeline did but why.
Adding a node — persistence, a translation pass, a second judge — is a wiring change rather
than a rewrite of the orchestrator.

**Why `threshold_detector` is a node rather than just an edge function.** Making the decision
inside a node puts `decision` and `terminal_reason` into state where the API can return them.
The conditional edge is then a one-line lookup.

**Async throughout.** Nodes are `async def` and use `ainvoke`, so nothing blocks the event
loop and the API can serve concurrent requests without a thread pool.

**Clients built once.** `ChatOpenAI` instances are constructed per role at startup and cached,
rather than per call.

**No checkpointer.** A run is single-shot and stateless. Adding `MemorySaver` in
[`app/graph/builder.py`](app/graph/builder.py) is the only change needed for resumable runs.

---

