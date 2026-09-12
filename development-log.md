# Development Log

Append-only human changelog. One entry per task outcome — completed, deprecated, or
failed. Task files (tasks/) are the spec; this is the running record of what actually
happened. Written when there is something to say; never parsed back.

## 2026-09-12 — Extend toml_writer to emit nested tables (completed)
- toml_writer can now emit nested/dotted tables. Suite 188 pass (from 184).

## 2026-09-12 — Add the failed state to the task workflow (completed)
- TaskState.failed added; in_progress -> failed, failed -> pending/deprecated.
  Suite 193 pass (from 188).

## 2026-09-12 — Wire toml_writer into task.py (completed)
- Task.to_toml delegates to toml_writer; the inline _format_toml_value was removed.
  Suite 193 pass (refactor, no behavior change).

## 2026-09-12 — Add sections to the Task model and keep them out of render (completed)
- Section model added; Task.sections serializes as [sections.1], [sections.2], ...
  and is never rendered. Suite 198 pass (from 193).

## 2026-09-12 — Add the record-failure subcommand (completed)
- main.py record-failure appends a Section, keeps the task in pending, and appends
  here. Suite 209 pass (from 198).

## 2026-09-12 — Document the failed state in command.md (completed)
- command.md documents the failed state and the record-failure workflow. Docs only.

## 2026-09-12 — Update SKILL.md and README.md for TOML and the failed state (completed)
- SKILL.md/README.md brought up to date for TOML task files and the failed state.
  Suite 209 pass.

## 2026-09-12 — Split Section into Failure and Revision subclasses (deprecated)
- Superseded: rather than split Section into Failure/Revision subclasses, keep a
  single Section keyed by type (see the rename below). Deprecated in favor of
  2026-09-12T11-17-33-rename-the-section-field-kind-to-type.toml.

## 2026-09-12 — Rename the section field kind to type (completed)
- Section.kind -> type, matching the top-level task vocabulary. Four one-line edits
  across scripts/ and tests/. Suite 209 pass.
