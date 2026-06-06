# track-tasks-skill

A skill for managing work as structured task files. Nothing revolutionary — just a consistent format that keeps Claude honest about what it's doing and why, and makes it easy to hand work off to a local model.

## Usage

Create a task:
```
create a task to refactor the auth module
```

Delegate to pond:
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
