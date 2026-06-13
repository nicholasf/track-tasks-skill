# Track Tasks

Tasks are Markdown files that capture a unit of work before it begins. They live in `tasks/pending/` while in progress and move to `tasks/completed/` when done. A corresponding entry is added to `development-log.md`.

## Dependencies

- [load-topology-skill](https://github.com/nicholasf/load-topology-skill) — provides `context_window` (from `## Model State`) and `tok/s` (from `## LLM Benchmarks`) used in time estimation
- [ask-remote-agent-skill](https://github.com/nicholasf/ask-remote-agent-skill) — provides `reasoning_buffer` (from `## Agent State`) and is the delegation mechanism for agent-runtime targets (Hermes, Goose)
- [ask-remote-llm-skill](https://github.com/nicholasf/ask-remote-llm-skill) — provides the tokenisation endpoint (`/tokenize` for llama-server, `/api/tokenize` for Ollama) used in time estimation; also used for direct LLM delegation without an agent runtime

## When to create a task

Write a task file when the work is substantial enough that:
- it touches multiple files or has distinct stages, **or**
- it requires a decision to be recorded before execution, **or**
- it will be handed off to a different model for execution

For small, self-contained edits, just do the work.

## Model assignment

Every task file must include a `model` field specifying which model should execute it.

**Token economisation:** A key reason to delegate a task to a local LLM node is to avoid spending cloud API tokens on work that does not require high-level reasoning. Cloud model tokens are expensive; local model inference is effectively free. The orchestrating agent should design the task precisely and hand off execution to a cheaper model, reserving its own involvement for architecture, ambiguous decisions, and review.

**If a `topology.md` file exists in the project root, read it before assigning a model.** It describes the available models, their capabilities, and their intended use cases. Use it to make an informed assignment.

If no `topology.md` is present, use your best judgement and note the assumption in the task file.

General guidance (override with topology.md when present):

| Work type | Suggested assignment |
|---|---|
| Architecture, design, ambiguous problems | Cloud reasoning model (e.g. Claude Sonnet) |
| Mechanical execution: schema changes, renames, wiring | Local coding model (e.g. Qwen2.5-Coder 32B) |
| Small, self-contained edits | Either; skip the task file |

## Task file format

Task files are created by `create.py`, not written directly. `create.py` runs
preflight estimation and writes the file atomically — no task exists without a
preflight result.

### Creating a task

Collect the task fields as a JSON object and pass them to `create.py`:

```bash
echo '{
  "title": "Add logging to gate",
  "goal": "Gate logs all requests at INFO level.",
  "model": "qwen3-coder-30b on pond — mechanical wiring",
  "agent": "pond-qwen-hermes",
  "background": "Logging is currently absent from the gate service.",
  "changes": ["Add structlog to gate/requirements.txt", "Wire logging in gate/main.py"],
  "files_to_read": ["backend/gate/main.py", "backend/gate/requirements.txt"],
  "open_questions": [],
  "recommended_approach": "Install structlog first, then wire at the request boundary.",
  "done_when": ["All requests log at INFO", "uv run pytest passes"]
}' | "${SKILLS_HOME:-$HOME/.agents/skills}/track-tasks-skill/.venv/bin/python3" \
     "${SKILLS_HOME:-$HOME/.agents/skills}/track-tasks-skill/scripts/create.py" \
     --hostname pond \
     --backend llama-server \
     --agent hermes \
     --cwd "$(pwd)"
```

`create.py` prints the path of the written file to stdout.

### Arguments

| Argument | Default | Description |
|---|---|---|
| `--hostname` | *(empty)* | Inference node for remote tokenizer and topology lookups. Omit to use local tokenizer. |
| `--backend` | `llama-server` | `llama-server` or `ollama` |
| `--agent` | `hermes` | Agent name for reasoning buffer lookup in topology |
| `--model` | *(empty)* | Model name for tok/s lookup (required for Ollama) |
| `--local` | false | Force `LocalTokenizer` even if a remote hostname is supplied |
| `--cwd` | current dir | Project root — where `tasks/pending/` will be created |
| `--input` | stdin | Path to a JSON file instead of reading from stdin |

### Required JSON fields

| Field | Type | Description |
|---|---|---|
| `title` | string | Short title |
| `goal` | string | One sentence — what will be true when this is done |
| `model` | string | Model name and rationale |
| `agent` | string | Agent handle (e.g. `pond-qwen-hermes`) |

### Optional JSON fields

`background`, `changes` (list), `files_to_read` (list), `open_questions` (list),
`recommended_approach`, `done_when` (list). All default to empty.

### Preflight values

`create.py` always populates the `## Pre-flight` section before writing:

| Value | Meaning |
|---|---|
| `## Pre-flight ⏳ L1 ...` | Estimated via remote or local tokenizer |
| `unavailable-via-remote` | Remote tokenizer targeted but unreachable |
| `unavailable-via-local` | Local tokenizer (tiktoken) also failed |

L3 tasks should be broken into a programme task before delegation.

## Programme tasks

A **programme task** coordinates a group of related sub-tasks. Use one when the full work spans multiple LLM node runs that are too large to delegate as a single task.

### Programme file format

Keep the programme under 20 lines. It is an index, not a spec — the spec lives in the sub-tasks.

```markdown
# <Title>

**Type:** programme
**Created:** <YYYY-MM-DD HH:MM:SS>
**Status:** in-progress

## Goal
One sentence.

## Sub-tasks
- [ ] [<slug>](../pending/<timestamp>-<slug>.md)
- [ ] [<slug>](../pending/<timestamp>-<slug>.md)
```

Check off each item as the sub-task is completed. Mark the programme `completed` when all sub-tasks are checked.

### Sub-task file format

Keep each sub-task under 40 lines. Use the standard task format plus two extra fields at the top:

```
**Type:** sub-task
**Parent:** <timestamp>-<programme-slug>.md
```

### Context economy rules

These rules apply to both programme tasks and sub-tasks:

1. **Only write what the executing model cannot derive.** If it can answer by running `read_file` or `grep`, leave it out.
2. **No file contents.** Reference file paths; let the model read them.
3. **No repeated background.** The programme holds the goal; sub-tasks hold only the constraints for their slice.
4. **No pseudocode close to real code.** Describe behaviour and return types; the model writes the implementation.

### Workflow

1. The orchestrating agent writes the programme task file and all sub-task files.
2. The orchestrating agent delegates one sub-task at a time via `ask-foreign-agent`.
3. After each sub-task completes, check it off in the programme file and move it to `tasks/completed/`.
4. When all sub-tasks are checked off, mark the programme `completed` and move it to `tasks/completed/`.

## What belongs in a task file — and what does not

A task file is a **specification**, not an implementation. The executing model writes the code; the task file tells it what to write.

**Include:**
- File paths to create or modify
- Interfaces, method signatures, and type contracts (what the code must satisfy)
- Behaviour constraints and invariants (e.g. "hash with SHA-256 before storing", "return 401 if the header is absent")
- Known gotchas or non-obvious ordering constraints
- Verifiable acceptance criteria

**Do not include:**
- Working implementation code — not even as a "starting point" or "example". The executing model will shadow it verbatim and the orchestrating model has done the work for free.
- File contents that the model can derive from the specification
- Pseudocode that is close enough to real code that the model will copy it rather than reason about it

If you catch yourself writing a complete function body, stop. Replace it with a sentence describing what the function must do and what it must return.

## Estimate time

Invoke when the user runs `/track-tasks estimate-time <description or file path>`, or says "estimate time", "how long will this take", "what's the difficulty", "rate this task", or "preflight this task".

Before delegating a task, estimate its token cost and difficulty rating so the user knows what to expect. If the inference backend is reachable, run `preflight.py` directly:

```bash
"${SKILLS_HOME:-$HOME/.agents/skills}/track-tasks-skill/.venv/bin/python3" \
  "${SKILLS_HOME:-$HOME/.agents/skills}/track-tasks-skill/scripts/preflight.py" \
  tasks/pending/<timestamp>-<slug>.md \
  --hostname <node> \
  --backend llama-server \
  --agent hermes \
  --write
```

`--write` appends the result to the task file in place. Report the rating line to the user:

```
⏳ L1 (~67s) — fits comfortably, safe to delegate
```

If the inference backend is not reachable, estimate token counts using ~4 characters per token as a heuristic, read the task file and any listed files yourself, and report an approximate rating with a note that it is estimated.

### How the estimate is built

```
estimated_total = spec_tokens + file_tokens + reasoning_buffer
```

| Term | Source | How |
|---|---|---|
| `spec_tokens` | inference backend | tokenise the task file via `/tokenize` (llama-server) or `/api/tokenize` (Ollama) — provided by **ask-remote-llm-skill** |
| `file_tokens` | inference backend | tokenise each path listed under `## Files to read before starting`; sum the counts |
| `reasoning_buffer` | topology.md `## Agent State` | written by **ask-remote-agent-skill** `topology` subcommand; preserved across `load-topology discover` runs |
| `context_window` | topology.md `## Model State` | probed by **load-topology-skill** `discover` from llama-server `/props` or Ollama `/api/show` |
| `tok/s` | topology.md `## LLM Benchmarks` | measured by **load-topology-skill** `benchmark` subcommand |

### Difficulty rating

Thresholds are relative to the `context_window` of the target node, read from `topology.md`. If topology is not available, fallback thresholds of 25K (L1) and 40K (L2) apply.

| Rating | Level | Estimated tokens | Meaning |
|---|---|---|---|
| ⏳ | L1 | < 40% of context window | Quick — fits easily, safe to delegate |
| ⏳⏳ | L2 | 40–60% of context window | Moderate — snug, watch for overflow |
| ⏳⏳⏳ | L3 | > 60% of context window | Long — split into sub-tasks before sending |

L3 tasks should be broken into a programme task with sub-tasks before delegation.

### Example output

```
## Pre-flight ⏳ L1 (~67s)

- Spec: 713 tokens
- Files: schema.sql (1,240), 000003.up.sql (180), README.md (320) → 1,740 total
- Reasoning buffer: 12,000 (estimated)
- Estimated total: ~14,453 tokens
- Complexity: L1 — fits comfortably in a 65K window
- Context window: 65,536 — fits
- Time estimate: ~67s at 215 t/s
```

---

## Delegating to an LLM node

Use ask-foreign-agent in bridge mode. The remote agent has tools to read the local filesystem directly — pass the task file path in the message rather than embedding its contents.

```bash
"${SKILLS_HOME:-$HOME/.agents/skills}/ask-foreign-agent-skill/.venv/bin/python3" \
  "${SKILLS_HOME:-$HOME/.agents/skills}/ask-foreign-agent-skill/agent.py" \
  --cwd "$(pwd)" \
  "Execute the task at tasks/pending/<timestamp>-<slug>.md in full. Read the file first, implement everything described, and fill in the ## Results section when done."
```

Check the topology (load-topology-skill) to confirm the assigned model is running before delegating. Run pre-flight first for any task larger than a trivial edit.

## Executing a task

1. Read the task file fully before starting.
2. If `topology.md` exists, confirm the assigned model matches what is currently available.
3. Work through the **Changes** section in the order given by **Recommended approach**.
4. Resolve any **Open questions** encountered during execution; note the decision in the file.
5. Verify every item in **Done when** before declaring the task complete.

## Reviewing a delegated task

When a task was executed by a delegated local model, the reviewing orchestrating agent must **not** read the full changed files — doing so consumes the API tokens that delegation was intended to save. Instead:

1. Read only the **Results** section of the task file (filled in by the executing model).
2. Run or confirm the acceptance commands listed in **Done when** (test counts, typecheck). The test suite is the primary correctness signal.
3. Present a short summary to the user:
   - What changed (file list and counts, not contents)
   - Test results (suite count, pass/fail)
   - Any decisions made during execution
4. Wait for the user to confirm before marking the task complete. The user reviews the code directly if they wish.

## Correcting a delegated task

When the output has concrete errors, do not fix them directly — send the task back with a correction spec appended to the task file. This keeps the full review/correction history in one place.

1. Add a `## Corrections — Round N` section at the bottom of the task file (above `## Results`).
2. List each error as a numbered item. Be specific: state what was wrong and exactly what the correct behaviour is. Do not leave room for interpretation.
3. Re-delegate using the same ask-foreign-agent command.
4. Repeat until the output is correct, incrementing the round number each time.
5. Apply any trivial mechanical fixes yourself (e.g. missing timeout values, a single renamed field) rather than burning another round — note what you changed in `## Results`.

## Show subcommand

Invoke when the user runs `/track-tasks show`, "show tasks", "list tasks", "show completed tasks", or "show deprecated tasks".

Run:

```bash
python3 "${SKILLS_HOME:-$HOME/.agents/skills}/track-tasks-skill/scripts/show.py" \
  [pending|completed|deprecated] \
  [--page N] \
  [--per-page N] \
  --cwd "$(pwd)"
```

- Default state is `pending`. Accept `completed` or `deprecated` as the first positional argument.
- Default page size is 20. Pass `--per-page` to override.
- Pass `--page N` to navigate multi-page results.

Print the table output directly to the user. If the directory does not exist, report it clearly.

## Deprecating a task

When a task is superseded before completion — replaced by a programme task, a better-scoped sub-task, or a changed approach — mark it deprecated rather than completed.

1. Update its **Status** line to `deprecated`.
2. Add a `**Deprecated by:** <timestamp>-<slug>.md` line immediately below.
3. Move the file to `tasks/deprecated/`.
4. Append a concise entry to `development-log.md` noting what the task was and why it was deprecated.

Do not use `tasks/completed/` for deprecated tasks. Completed means the work was done; deprecated means it was abandoned in favour of something else.

## Completing a task

When all **Done when** items are checked and (for delegated tasks) the user has confirmed:

1. Move the file: `mv tasks/pending/<timestamp>-<slug>.md tasks/completed/<timestamp>-<slug>.md`
   The timestamp prefix is preserved so completed tasks are ordered chronologically in a directory listing.
2. Update its **Status** line to `completed`.
3. Append a concise summary to `development-log.md` covering what changed and any decisions made during execution.

## Directory structure

```
tasks/
  pending/      # tasks not yet complete
  completed/    # finished tasks, kept for reference
  deprecated/   # tasks superseded before completion
development-log.md
```

Create these if they do not exist.
