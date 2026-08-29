# track-tasks-skill

Manage units of work as structured TOML files — a typed `Task` model round-trips end to end, so nothing is ever parsed back out of prose. Tasks live in `tasks/pending/` while in progress and move to `tasks/completed/` when done. Programme tasks group related sub-tasks for larger workloads.

This skill is part of a small ecosystem:

- [load-topology-skill](https://github.com/nicholasf/load-topology-skill) — discovers the machines on your network, names them, and tracks which LLMs are running on each. A machine running a qwen model is referred to as `pond-qwen`; add the agent platform to get an **agent handle** like `pond-qwen-hermes`.
- [ask-remote-llm](https://github.com/nicholasf/ask-remote-llm-skill) — sends a question or task to an LLM on one of those machines and returns the response.
- [ask-remote-agent](https://github.com/nicholasf/ask-remote-agent-skill) — delegates a task to an autonomous agent on a remote machine using its agent handle. The agent executes independently and returns a git diff.

**track-tasks-skill** ties these together: write a task, delegate it to an agent handle, review the diff, mark it done.

---

## Subcommands

| Subcommand | Description |
|---|---|
| `create` | Write a new task file to `tasks/pending/` with a pre-flight token estimate |
| `start` | Transition a task to `in_progress` and record its execution mode (see [Execution modes](#execution-modes)) |
| `complete` | Move a task to `tasks/completed/` and record a summary in `development-log.md` |
| `deprecate` | Move a task to `tasks/deprecated/` when it is superseded before completion |
| `mark-as-hallucinated` | Move a task to `tasks/hallucinated/` when the executing LLM claimed completion but produced no real output |
| `show` | Print a summary table of tasks in a given state (`pending`, `completed`, `deprecated`, `hallucinated`) |
| `estimate-tokens` | Count token cost across the task spec and referenced files, rate complexity, and estimate duration |

---

## Examples

```
/track-tasks
```

Full workflow — create, delegate, or review tasks. Common natural language triggers:

```
create a task to refactor the auth module
write a task for adding pagination to the user list
what tasks are pending
mark this task complete
```

### Delegate a task to a remote node

Agent handles identify a remote agent as `<machine>-<llm>-<agent>` — e.g. `pond-qwen-hermes` means the machine `pond`, running `qwen`, via the `hermes` agent. Load the topology first to see what handles are available on your network.

```
write a task to add input validation to the API and send it to pond-qwen-hermes
```

The remote agent executes the task autonomously. Results come back as a **git diff** — the local agent reviews the diff and confirms before marking the task complete.

> PRs are not yet automated and will be addressed separately.

### Estimate time before delegating

Before sending a task to a remote node, run the `estimate-time` subcommand with a natural language description of the work or a path to an existing task file:

```
/track-tasks estimate-time add input validation to the payments API
```

```
/track-tasks estimate-time tasks/pending/2026-06-08T10-00-00-auth-refactor.toml
```

The response shows a difficulty rating and estimated duration:

```
⏳⏳ L2 (~120s) — moderate, snug but fits a 65K window
```

Ratings are relative to the target node's context window (read from `topology.toml`). If the inference backend is not reachable, the skill falls back to a character-count heuristic and marks the estimate as approximate.

### Check pending work

```
what tasks are pending
```

### Review a completed task

```
review the results of the auth refactor task
```

The local agent reads the `results` field filled in by the remote model, runs the acceptance commands, and presents a summary — without reading every changed file (which would spend the tokens that delegation was meant to save).

---

## How it works

A task file is a specification written before execution. The local agent writes it; a remote agent (or the local agent itself) executes it. When delegated:

1. A task file is written to `tasks/pending/` with a goal, changes, and acceptance criteria.
2. **Estimate time** rates the task's token cost and difficulty before it is sent.
3. The task is sent to a remote agent handle (e.g. `pond-qwen-hermes`) via [ask-remote-agent](https://github.com/nicholasf/ask-remote-agent-skill).
4. The remote agent executes the task, fills in `results`, and the local agent reviews the **git diff**.
5. Once confirmed, the task moves to `tasks/completed/` and an entry is added to `development-log.md`.

**Token economy:** local LLM inference is effectively free; cloud model tokens are not. The pattern is: cloud model designs and reviews, local model executes.

---

## Execution modes

A task's `execution_mode` field records how it's actually being worked on — set via `start`, which also transitions the task to `in_progress`:

| Mode | How it runs |
|---|---|
| `ask_llm` | Bridge mode via [ask-remote-llm](https://github.com/nicholasf/ask-remote-llm-skill) — shared tools, no independent git checkout |
| `ask_agent` | Autonomous runtime via [ask-remote-agent](https://github.com/nicholasf/ask-remote-agent-skill) on a remote node, using its own git checkout |
| `local` | The current/local agent executes it directly (default) |
| `local_worktree` | Another local agent works in its own `git worktree`, so several agents can work on independent branches of the same repo at once |

```
main.py start tasks/pending/<task>.toml --mode local_worktree \
  --worktree-path ../wt-add-logging --branch task/add-logging
```

For `local_worktree`, `start` runs `git worktree add <path> -b <branch>` and records the path and
branch on the task. It only creates the worktree — launching the agent that works in it is up to
whatever orchestrator is running (e.g. an `Agent` tool with worktree isolation), the same way
`start`ing `ask_llm`/`ask_agent` modes doesn't itself invoke those skills. Completing or
deprecating a task does **not** remove its worktree automatically — `complete` prints a reminder
(`git worktree remove <path>`) so it isn't silently forgotten. `show` includes a `Mode` column so
you can see what's running where across many concurrent tasks.

---

## Estimate time

Ask "estimate time for this task", "how long will this take", or "what's the difficulty" before delegating. `main.py estimate-tokens` counts tokens across the task spec, all files it needs to read, and the model's reasoning overhead, then rates the task **relative to the context window of the target node**:

| Rating | Level | Estimated tokens | Meaning |
|---|---|---|---|
| ⏳ | L1 | < 40% of context window | Quick — fits easily, safe to delegate |
| ⏳⏳ | L2 | 40–60% of context window | Moderate — snug, watch for overflow |
| ⏳⏳⏳ | L3 | > 60% of context window | Long — split into sub-tasks before sending |

The context window is read from `topology.toml` for the target node and model, written there by [load-topology-skill](https://github.com/nicholasf/load-topology-skill). This means an L3 threshold differs by agent handle: a node with a 65K context window rates L3 at >39K tokens, while one with a 128K window rates L3 at >78K tokens. If the topology is not available, fallback thresholds of 25K (L1) and 40K (L2) apply.

The rating and estimated duration appear at the top of the `## Pre-flight` section written into the task file:

```
## Pre-flight ⏳⏳ L2 (~120s)

- Spec: 4,210 tokens
- Files: schema.sql (1,240), api.py (8,430) → 9,670 total
- Reasoning buffer: 12,000 (estimated)
- Estimated total: ~25,880 tokens
- Complexity: L2 — safe but snug — watch for overflow
- Context window: 65,536 — fits
- Time estimate: ~120s at 215 t/s
```

The duration estimate comes from `estimated_total ÷ tok/s`, where throughput is measured by [load-topology-skill](https://github.com/nicholasf/load-topology-skill)'s benchmark subcommand and stored in `topology.toml`.

---

## Task states

| State | Location | Meaning |
|---|---|---|
| `planned` / `in-progress` | `tasks/pending/` | Active work |
| `completed` | `tasks/completed/` | Successfully finished |
| `deprecated` | `tasks/deprecated/` | Superseded before completion |
| `hallucinated` | `tasks/hallucinated/` | The executing LLM claimed to complete the task but produced no real output |

A task is marked `hallucinated` when the executing LLM reports that it completed the work — describing changes, tests, and results — but no actual output exists: no files written, no diff produced, no tests run. The remote agent may return a confident, detailed summary that is entirely fabricated.

The `mark-as-hallucinated` subcommand moves the task to `tasks/hallucinated/` and records:

- the full solution text the LLM claimed to produce
- the agent handle that produced the hallucination
- the agent handle that caught and reported it
- the reason it was judged a hallucination

This preserves evidence for later analysis of which agent handles, models, or task shapes are most prone to hallucination.

---

## Programme tasks

A programme task coordinates a group of related sub-tasks — use one when the full work is too large to delegate as a single task. It is an index (under 20 lines); the spec lives in the sub-tasks.

```
create a programme task for the payment module refactor with sub-tasks for schema, API, and tests
```

---

## Dependencies

- [load-topology-skill](https://github.com/nicholasf/load-topology-skill) — topology is the source of truth for which nodes and models are available
- [ask-remote-agent](https://github.com/nicholasf/ask-remote-agent-skill) — used to delegate task execution to a remote node
