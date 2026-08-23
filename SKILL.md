---
name: track-tasks
description: Manage work as structured task files in tasks/pending/ and tasks/completed/. Triggers on "create a task", "write a task for", "what tasks are pending", "show tasks", "list tasks", "show completed tasks", "mark this task complete", "update the task", "estimate time for this task", "what's the time estimate", "how long will this take", "what's the difficulty rating".
argument-hint: "[show [pending|completed|deprecated] | estimate-time <task description or file path>]"
depends_on:
  - load-topology-skill
---

## NOTE

**Always invoke this skill via its slash command — never construct the shell commands manually.**

When the user asks to create a task, delegate work, show tasks, or complete a task via natural language, invoke `/track-tasks` (with the appropriate subcommand if needed). The skill's own logic handles topology checks, preflight estimation, backend selection, and correct invocation. Improvising the shell commands from memory bypasses these safeguards and leads to errors.

## Dependencies

- [load-topology-skill](https://github.com/nicholasf/load-topology-skill)

Tasks are Markdown files in `tasks/pending/` while in progress and `tasks/completed/` when done. A corresponding entry goes in `development-log.md`. Invoke `/track-tasks` for the full workflow.
