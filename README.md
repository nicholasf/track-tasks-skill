# track-tasks-skill

A skill for managing work as structured task files. Nothing revolutionary — just a consistent format that keeps Claude honest about what it's doing and why, and makes it easy to hand work off to a local model.

## Topology and task delegation

Task delegation relies on [load-topology-skill](https://github.com/nicholasf/load-topology-skill). The topology file describes the machines on your network and which of them are running LLM inference servers (llama-server or Ollama). When assigning a task to a model, the task-tracking skill reads the topology to identify what nodes are available and what models they are running.

A node in the topology with a role of `llm` is a candidate for delegation. Before sending a task, the inference server on that node must be running and reachable. The skill refers to these nodes by hostname — "pond" in the examples below is simply the hostname of a machine in the topology running llama-server on port 9337. Your topology may use different hostnames and different models.

Delegation works over the node's OpenAI-compatible API endpoint (e.g. `http://pond:9337`). The task file is read and embedded in the request payload; the remote model executes the task and fills in the Results section. Claude then reviews the output rather than doing the work itself, which keeps cloud API token use low.

## Usage

Create a task:
```
create a task to refactor the auth module
```

Delegate to an LLM node in the topology:
```
write a task for adding pagination to the user list and send it to pond
```

Check what's pending:
```
what tasks are pending
```

Mark complete:
```
mark this task complete
```

## How it works

Tasks live as markdown files in `tasks/pending/` and move to `tasks/completed/` when done. Each task specifies a model assignment, a goal, changes, and verifiable done criteria. Completed tasks are logged to `development-log.md`.

See `SKILL.md` for the full format and delegation instructions.

## Dependencies

Requires [load-topology-skill](https://github.com/nicholasf/load-topology-skill) — the topology file is the source of truth for which nodes and models are available for task delegation.
