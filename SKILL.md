---
name: task-tracking
description: Manage work as structured task files in tasks/pending/ and tasks/completed/. Triggers on "create a task", "write a task for", "what tasks are pending", "mark this task complete", "update the task", "estimate time for this task", "what's the time estimate", "how long will this take", "what's the difficulty rating".
argument-hint: "[estimate-time <task description or file path>]"
depends_on:
  - load-topology-skill
---

## Dependencies

- [load-topology-skill](https://github.com/nicholasf/load-topology-skill)

Tasks are Markdown files in `tasks/pending/` while in progress and `tasks/completed/` when done. A corresponding entry goes in `development-log.md`. Invoke `/track-tasks` for the full workflow.
