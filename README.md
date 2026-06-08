# track-tasks-skill

Manage units of work as structured Markdown files. Tasks live in `tasks/pending/` while in progress and move to `tasks/completed/` when done. Programme tasks group related sub-tasks for larger workloads.

This skill is part of a small ecosystem:

- [load-topology-skill](https://github.com/nicholasf/load-topology-skill) — discovers the machines on your network, names them, and tracks which LLMs are running on each. A machine running a qwen model is referred to as `pond-qwen`; add the agent platform to get an **agent handle** like `pond-qwen-hermes`.
- [ask-remote-llm](https://github.com/nicholasf/ask-remote-llm-skill) — sends a question or task to an LLM on one of those machines and returns the response.
- [ask-remote-agent](https://github.com/nicholasf/ask-remote-agent-skill) — delegates a task to an autonomous agent on a remote machine using its agent handle. The agent executes independently and returns a git diff.

**track-tasks-skill** ties these together: write a task, delegate it to an agent handle, review the diff, mark it done.

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

Before sending a task to a remote node, ask for a time estimate. The skill tokenises the task and any files it needs to read, then rates it relative to the target node's context window:

```
estimate time for tasks/pending/2026-06-08T10-00-00-add-pagination.md
```

```
how long will the auth refactor task take on pond-qwen-hermes
```

The response shows a difficulty rating and estimated duration:

```
⏳⏳ L2 (~120s) — moderate, snug but fits a 65K window
```

If the inference backend is not reachable, the skill falls back to a character-count heuristic and marks the estimate as approximate.

### Check pending work

```
what tasks are pending
```

### Review a completed task

```
review the results of the auth refactor task
```

The local agent reads the `## Results` section filled in by the remote model, runs the acceptance commands, and presents a summary — without reading every changed file (which would spend the tokens that delegation was meant to save).

---

## How it works

A task file is a specification written before execution. The local agent writes it; a remote agent (or the local agent itself) executes it. When delegated:

1. A task file is written to `tasks/pending/` with a goal, changes, and acceptance criteria.
2. **Estimate time** rates the task's token cost and difficulty before it is sent.
3. The task is sent to a remote agent handle (e.g. `pond-qwen-hermes`) via [ask-remote-agent](https://github.com/nicholasf/ask-remote-agent-skill).
4. The remote agent executes the task, fills in `## Results`, and the local agent reviews the **git diff**.
5. Once confirmed, the task moves to `tasks/completed/` and an entry is added to `development-log.md`.

**Token economy:** local LLM inference is effectively free; cloud model tokens are not. The pattern is: cloud model designs and reviews, local model executes.

---

## Estimate time

Ask "estimate time for this task", "how long will this take", or "what's the difficulty" before delegating. `preflight.py` counts tokens across the task spec, all files it needs to read, and the model's reasoning overhead, then rates the task **relative to the context window of the target node**:

| Rating | Level | Estimated tokens | Meaning |
|---|---|---|---|
| ⏳ | L1 | < 40% of context window | Quick — fits easily, safe to delegate |
| ⏳⏳ | L2 | 40–60% of context window | Moderate — snug, watch for overflow |
| ⏳⏳⏳ | L3 | > 60% of context window | Long — split into sub-tasks before sending |

The context window is read from `topology.md` for the target node and model, written there by [load-topology-skill](https://github.com/nicholasf/load-topology-skill). This means an L3 threshold differs by agent handle: a node with a 65K context window rates L3 at >39K tokens, while one with a 128K window rates L3 at >78K tokens. If the topology is not available, fallback thresholds of 25K (L1) and 40K (L2) apply.

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

The duration estimate comes from `estimated_total ÷ tok/s`, where throughput is measured by [load-topology-skill](https://github.com/nicholasf/load-topology-skill)'s benchmark subcommand and stored in `topology.md`.

---

## Task states

| State | Location |
|---|---|
| `planned` / `in-progress` | `tasks/pending/` |
| `completed` | `tasks/completed/` |
| `deprecated` | `tasks/deprecated/` |

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
