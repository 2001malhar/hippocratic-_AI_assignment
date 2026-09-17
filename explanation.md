# Explanation

A walkthrough of the system: what it does, how a request flows through it, how the code is
organised, and what each module and function is responsible for.

---

## 1. Overview

The application generates bedtime stories for children aged 5–10. A request is planned,
written, scored against a rubric, revised if it falls short, and published once it meets the
acceptance policy.

It runs as a single process serving three interfaces:

- a JSON API under `/api/v1`
- a Gradio UI at `/ui`
- a command-line entrypoint (`cli.py`)

All three call the same service object, which runs the same compiled LangGraph graph.

---

## 2. Request flow

A single request moves through the system like this:

1. **Entry.** The API handler, the Gradio click handler or the CLI collects a story request,
   a style key and an optional revision budget.
2. **Service.** `StoryService.generate()` assigns a `run_id`, expands the style key into a
   prompt fragment, builds the initial graph state and invokes the graph.
3. **Graph.** The six nodes run, looping between `judge` and `refine` until the acceptance
   policy is satisfied or the revision budget is spent.
4. **Response.** The service converts the terminal graph state into a `StoryResponse`
   containing the story, the plan, the score card and the per-iteration judge trace.
5. **Presentation.** The API returns it as JSON; the UI renders it across the story panel and
   the debug accordion; the CLI prints it.

---

## 3. The graph

```
START ──▶ plan_story ──▶ generate_story ──▶ judge ──▶ threshold_detector
                                             ▲                  │
                                             │   below bar      │  meets bar, or
                                             │                  │  budget spent
                                             └──── refine ◀──────┼──────▶ publish ──▶ END
```

The graph is defined in [`app/graph/builder.py`](app/graph/builder.py). Edges from `START`
through `judge` are fixed. `threshold_detector` has a conditional edge that routes to either
`publish` or `refine`. `refine` returns to `judge`, forming the revision cycle. `publish`
leads to `END`.

Four nodes call the model; two are plain Python.

### State

[`app/graph/state.py`](app/graph/state.py) defines `StoryState`, a `TypedDict` carrying:

| Group | Fields |
|---|---|
| Inputs | `run_id`, `user_request`, `style`, `max_revisions` |
| Working | `plan`, `story`, `scorecard`, `feedback` |
| Loop bookkeeping | `iteration`, `revisions_used`, `history` |
| Best draft seen | `best_story`, `best_scorecard`, `best_iteration` |
| Routing / output | `decision`, `terminal_reason`, `published_story`, `published_title` |

`history` uses an `operator.add` reducer, so each judge pass appends a record and the full
revision trail is preserved. Every other field is last-write-wins.

`initial_state()` builds the starting state for a run.

Models are stored as dictionaries because LangGraph serialises state between steps; nodes
validate them back into Pydantic objects when they need typed access.

### Nodes

Each node is an `async def` that receives the whole state and returns a partial update.

**`plan_story`** — [`app/graph/nodes/plan_story.py`](app/graph/nodes/plan_story.py)

Calls the planner with the request and style, and validates the result into a `StoryPlan`.
If validation fails, it calls the planner a second time with the specific validation errors
included in the prompt, and raises `PlanValidationError` if that also fails. The helper
`_summarise()` renders a `ValidationError` compactly enough to embed in a prompt.
Returns `{"plan": ...}`.

**`generate_story`** — [`app/graph/nodes/generate_story.py`](app/graph/nodes/generate_story.py)

Calls the storyteller with the request, style and plan. Runs once per run; all later drafts
come from `refine`. Returns `{"story": ...}`.

**`judge`** — [`app/graph/nodes/judge.py`](app/graph/nodes/judge.py)

Calls the judge with the request, style, plan and current draft, validates the response into
a `JudgeVerdict`, then passes it to `score_story()` to produce a `ScoreCard`. Builds an
`IterationRecord` and returns `{"scorecard", "feedback", "iteration", "history"}`.

**`threshold_detector`** — [`app/graph/nodes/threshold_detector.py`](app/graph/nodes/threshold_detector.py)

Deterministic. Compares the current score card against the incumbent best using
`is_better()` and updates the `best_*` fields when the new draft wins. Then chooses a route:

```python
if scorecard.passed:                        -> publish, terminal_reason="passed_threshold"
elif revisions_used >= max_revisions:       -> publish, terminal_reason="max_revisions_exhausted"
else:                                       -> refine
```

Returns `{"decision", "terminal_reason", "best_*"}`. The budget branch bounds the cycle.

**`refine`** — [`app/graph/nodes/refine.py`](app/graph/nodes/refine.py)

Calls the reviser with the current draft, the judge's feedback, any content-flag violations
and the calming-ending result. Increments the revision counter. Returns
`{"story", "revisions_used"}`, and the graph routes back to `judge`.

**`publish`** — [`app/graph/nodes/publish.py`](app/graph/nodes/publish.py)

Deterministic. Takes the best draft recorded during the run, splits the title from the body,
logs the result and returns `{"published_story", "published_title", "scorecard", "story",
"terminal_reason"}`.

Two helpers handle title extraction:

- `_clean_title_line(line)` strips decoration from a candidate title line — wrapping
  characters (`"`, `'`, `*`, `_`, `#`, backticks, curly quotes) and `Title:` style labels.
  It peels, removes a label, then peels again, since the label appears both inside and
  outside the wrappers. Returns `""` if the line was only decoration.
- `split_title(story)` walks the leading lines, skipping blanks and lines that clean to
  nothing, and returns the first real title with the remainder as the body. A first line
  longer than 120 characters is treated as prose: it is truncated for display and the full
  text is kept as the body.

### Routing

[`app/graph/routing.py`](app/graph/routing.py) holds `route_after_threshold(state)`, which
reads `state["decision"]` and returns the next node name. It defaults to `"publish"`.

### Compilation

`build_graph()` wires the nodes and edges and compiles the graph. `get_graph()` caches the
compiled graph for the process. `render_mermaid()` returns a Mermaid diagram of the topology.
No checkpointer is configured; a run is single-shot and stateless.

The recursion limit is derived from the revision budget rather than left at the default:

```python
recursion_limit = 2 * (max_revisions + 1) + 6
```

---

## 4. Evaluation

[`app/services/evaluation.py`](app/services/evaluation.py) converts judge output into a
verdict. Every function in it is pure: no network calls, and the input verdict is not
mutated.

**`score_story(verdict, settings)`** produces a `ScoreCard`:

1. Reads the six rubric scores from the verdict.
2. If any content flag is set, clamps `emotional_safety` to at most `SAFETY_VETO_CEILING`
   (2.0) and records the tripped flags in `safety_violations`.
3. If `calming_ending_met` is false, clamps `bedtime_quality` to at most
   `CALMING_ENDING_CEILING` (3.0).
4. Averages the six scores into `overall_score`, rounded to two decimals.
5. Compares each gated metric against `settings.evaluation_policy` and collects any that fall
   short into `failed_metrics`.
6. Sets `passed` to true only when `failed_metrics` is empty **and** no content flag is set.

**`derive_rating(overall_score)`** maps the average onto a 1–5 star rating.

**`normalise_feedback(feedback)`** strips blanks and substitutes a generic note if the list is
empty, so the reviser always has something to act on.

**`is_better(candidate, incumbent)`** ranks two score cards to decide which draft to keep:
safe beats unsafe, then passing beats failing, then the higher average wins.

### The acceptance policy

`Settings.evaluation_policy` returns the metric-to-minimum mapping:

| Metric | Default minimum |
|---|---|
| `overall_score` | 4.0 |
| `request_adherence` | 4.0 |
| `age_appropriateness` | 4.0 |
| `emotional_safety` | 4.0 |
| `bedtime_quality` | 4.0 |

`story_quality` and `story_structure` are scored and included in the average, but are not
gated individually.

---

## 5. Prompts

[`app/prompts/`](app/prompts/) holds one module per role. Each exposes a `SYSTEM` constant and
a `build_prompt(...)` function that renders the user message.

**`planner.py`** — asks for a JSON plan with eight keys: `category`, `target_age`,
`characters`, `setting`, `tone`, `story_arc`, `lesson`, `bedtime_ending`. Also provides
`build_repair_prompt()`, which appends validation errors for the retry, and `format_plan()`,
which renders a plan as indented JSON for the downstream prompts.

**`storyteller.py`** — asks for a 400–700 word story with the title on the first line, a mild
challenge, sensory detail or dialogue, and a final section that grows quieter.

**`judge.py`** — asks for six 1–5 scores with per-dimension anchors, eight boolean content
flags, the story's final sentences quoted verbatim, a `calming_ending_met` ruling and 2–4
actionable feedback notes. The system prompt instructs the model not to compute the overall
score or decide whether the story passes.

**`reviser.py`** — supplies the draft and the feedback. When content flags were raised it adds
a mandatory safety-corrections section; when the calming-ending check failed it adds a
mandatory ending-correction section. `_bullets()` formats a sequence as a bulleted list.

---

## 6. LLM access

[`app/llm/client.py`](app/llm/client.py) builds one `ChatOpenAI` per role at startup.

`LLMRole` enumerates `planner`, `storyteller`, `judge`, `reviser`. `ROLE_CONFIG` maps each to
its sampling settings:

| Role | Temperature | Max tokens | JSON mode |
|---|---|---|---|
| planner | 0.35 | 700 | yes |
| storyteller | 0.8 | 1300 | no |
| judge | 0.15 | 900 | yes |
| reviser | 0.6 | 1300 | no |

- `get_llm(role)` returns the cached client for a role, applying
  `response_format: {"type": "json_object"}` where JSON mode is enabled.
- `invoke_text(role, system_prompt, prompt)` sends the messages, returns the stripped text,
  and converts any transport failure into an `LLMError`.
- `warmup()` builds every client at startup so a missing key surfaces at boot.
- `api_key_configured()` reports credential presence for the health endpoint.

[`app/llm/json_utils.py`](app/llm/json_utils.py) handles JSON responses. `gpt-3.5-turbo`
supports JSON mode but not `json_schema`, so a well-formed object is guaranteed while a
correctly shaped one is not. Four layers close that gap: JSON mode on the request, the
parsing below, one retry, and Pydantic validation at the node.

- `parse_json_response(raw_text)` strips code fences, attempts `json.loads`, and falls back to
  slicing between the first `{` and the last `}`. Raises `JSONParseError` if neither works or
  the result is not an object.
- `invoke_json(role, system_prompt, prompt)` calls the model and parses the reply, retrying
  once with `STRICT_JSON_SUFFIX` appended before giving up.

---

## 7. Schemas

[`app/schemas/story.py`](app/schemas/story.py) — the domain models.

- `SCORE_KEYS` — the six rubric dimensions in report order.
- `TerminalReason` — `passed_threshold` or `max_revisions_exhausted`.
- `Decision` — `publish` or `refine`.
- `StoryPlan` — the eight plan fields. A validator accepts a comma-joined string where a list
  is expected and splits it, since the model returns `"fox, bunny"` reasonably often.
- `ContentFlags` — the eight parental guideline booleans, plus `tripped()` returning the names
  of those that are set.
- `JudgeVerdict` — raw judge output. Validators coerce each score to a float clamped to
  1.0–5.0, treating a missing or non-numeric value as 1.0, and normalise `feedback` into a
  list of non-empty strings.
- `ScoreCard` — the scored result: six dimensions, `overall_score`, `rating`, `passed`,
  `content_flags`, `safety_violations`, `calming_ending_met`, `final_sentences`, `feedback`
  and `failed_metrics`. `scores()` returns just the six dimensions.
- `IterationRecord` — one judge pass: the iteration number, the draft and its score card.

[`app/schemas/api.py`](app/schemas/api.py) — the HTTP contracts: `StoryRequest`,
`IterationSummary`, `StoryResponse`, `StyleOption`, `HealthResponse` and `ErrorResponse`.

---

## 8. Services

[`app/services/story_service.py`](app/services/story_service.py) holds `StoryService`, the
single entry point for the API, the UI and the CLI.

- `generate(request, style, max_revisions)` assigns a run id, binds it for logging, resolves
  the revision budget, invokes the graph with a derived recursion limit, times the run and
  returns a `StoryResponse`.
- `_to_response(...)` converts terminal graph state into the response model, mapping each
  `IterationRecord` into an `IterationSummary`.

---

## 9. Configuration

[`app/settings.py`](app/settings.py) defines a `pydantic-settings` `Settings` class read from
the environment and `.env`, with `get_settings()` caching one instance per process.

Fields cover the API key, the model and its timeout and retry count, the revision budget, the
five thresholds, and the host, port and log level. Two computed properties derive from them:
`evaluation_policy` (the metric-to-minimum mapping) and `recursion_limit`.

Because the thresholds and the budget are settings rather than constants, the acceptance
policy can be adjusted through the environment.

[`app/styles.py`](app/styles.py) holds the style catalogue shared by all three interfaces:
`StyleKey` (`cozy`, `funny`, `magical`, `adventure`, `auto`), the `STYLES` tuple pairing each
key with a label and a prompt fragment, and the helpers `describe()`, `labels()` and
`key_for_label()`. Unrecognised input resolves to the auto description.

---

## 10. HTTP layer

[`app/application.py`](app/application.py) — `create_app()` configures logging, builds the
shared `StoryService`, registers the exception handlers and routers, adds a `/` redirect to
`/ui`, and mounts Gradio last so every API route is registered first. The `lifespan` context
manager runs `warmup()` at startup; if credentials are missing it logs the problem and still
serves, so `/healthz` and `/docs` remain reachable.

[`app/api/routes/`](app/api/routes/) — `health.py` exposes `GET /healthz`, which reports
status, version, model, graph readiness and credential presence without calling the model.
`stories.py` exposes `GET /api/v1/styles` and `POST /api/v1/stories`.

[`app/api/dependencies.py`](app/api/dependencies.py) — `get_story_service(request)` returns the
service held on `app.state`, so no request pays graph-compilation cost.

[`app/api/errors.py`](app/api/errors.py) — `register_exception_handlers(app)` maps any
`StoryAgentError` to its own status code and user-facing message, and catches everything else
as a 500. Technical detail goes to the log; the response body carries the message and the run
id.

[`app/core/exceptions.py`](app/core/exceptions.py) — the exception hierarchy. `StoryAgentError`
is the base, carrying `http_status` and `user_message`. Subclasses: `ConfigurationError` (500),
`LLMError` (503), `JSONParseError` (502, retaining the raw response), `PlanValidationError`
(502) and `JudgeValidationError` (502).

[`app/core/logging.py`](app/core/logging.py) — `configure_logging(level)` installs the logging
config. `set_run_id()` / `get_run_id()` manage a `ContextVar`, and `RunIdFilter` injects it
into every record, so one run can be followed across all six nodes.

---

## 11. Interfaces

**Gradio** — [`app/ui/gradio_app.py`](app/ui/gradio_app.py). `build_blocks(service)`
constructs the interface: a request textbox, a style dropdown, a max-revisions slider, a
generate button and examples on the left; the title, story and summary on the right; and a
collapsed debug accordion holding the plan JSON, a per-pass score table, the judge feedback
and the full response payload. The click handler calls the service directly in-process.
Presentation helpers: `_body_of()` (reuses `split_title` so the title is not repeated),
`_summary_markdown()`, `_history_rows()` and `_feedback_markdown()`.

**Server** — [`main.py`](main.py) creates the app at module level and runs uvicorn with the
configured host, port and log level.

**CLI** — [`cli.py`](cli.py). `parse_args()` defines `--request`, `--style`,
`--max-revisions`, `--debug`, `--json` and `--log-level`. `prompt_for_request()` and
`prompt_for_style()` drive the interactive path when the flags are absent. `run()` generates
the story and prints it; `print_story()` and `print_debug()` render the output, the latter
showing the plan, every judge pass with its scores and feedback, and the final totals.

---

## 12. Package structure

```
main.py                        uvicorn entrypoint (API + UI)
cli.py                         command-line entrypoint
app/
├── application.py             FastAPI factory, lifespan, Gradio mount
├── settings.py                configuration and the acceptance policy
├── styles.py                  style catalogue shared by all interfaces
├── core/
│   ├── exceptions.py          exception hierarchy with HTTP statuses
│   └── logging.py             run-id-aware logging
├── schemas/
│   ├── story.py               domain models
│   └── api.py                 HTTP request/response contracts
├── prompts/                   planner, storyteller, judge, reviser
├── llm/
│   ├── client.py              role-configured clients
│   └── json_utils.py          JSON parsing and retry
├── graph/
│   ├── state.py               StoryState
│   ├── builder.py             graph assembly and compilation
│   ├── routing.py             conditional edge
│   └── nodes/                 one module per node
├── services/
│   ├── evaluation.py          scoring, vetoes and the threshold gate
│   └── story_service.py       runs the graph, builds the response
├── api/
│   ├── dependencies.py        service injection
│   ├── errors.py              exception handlers
│   └── routes/                health and story endpoints
└── ui/
    └── gradio_app.py          Gradio Blocks
```

Dependencies point inward: nodes depend on prompts, LLM access and services; services depend
on schemas and settings; schemas depend on nothing. No module imports the API or UI layer, so
the graph runs the same under FastAPI, Gradio or the CLI.

---

