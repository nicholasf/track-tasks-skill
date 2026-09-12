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

## 2026-09-12 — Add Failure and Revision section classes

- Executed by qwen3.8-27b on pond via the ask-llm bridge. Added Failure and Revision as subclasses of Section in scripts/task.py: Failure declares only its type literal, Revision declares its type literal plus an instructions field defaulting to empty. Imported Literal from typing. Purely additive as specified — Section keeps all eight of its fields and Task.sections still holds Section, so the two new classes are defined but not yet used. Moving fields onto Failure and switching to a discriminated union is the next task. Verified independently: Section unchanged, Task.sections still dict[str, Section], Failure().type is 'failure', Revision().type is 'revision'.

## 2026-09-12 — Move section fields onto Failure and discriminate the union (failed)

- Five clean round trips reading files, then one ~20,700-token response over 8 minutes containing no tool call; stopped at 30,588 NOT truncated

## 2026-09-12 — Move section fields onto Failure and discriminate the union (revised)

- Superseded: Claude implemented this directly after four delegated attempts failed. No further attempt needed.

## 2026-09-12 — Move section fields onto Failure and discriminate the union

- Implemented directly by Claude after four delegated attempts failed. Section reduced to type/at_utc/at_local; agent, model, complexity, outcome and log moved onto Failure; agent and complexity added to Revision. Task.sections is now AnySection, a union discriminated on type, so from_toml restores the concrete subclass instead of silently downgrading to a bare Section. record_failure.py constructs a Failure. Added next_section_number, latest_section_number and latest_revision helpers, all filtering by type rather than branching on how many types exist.

## 2026-09-12 — Render the latest revision with the task

- Implemented directly by Claude as part of one pass across the remaining revision-workflow tasks.

## 2026-09-12 — Surface the latest section and record what completed a task

- Implemented directly by Claude as part of one pass across the remaining revision-workflow tasks.

## 2026-09-12 — Add the record-revision subcommand

- Implemented directly by Claude as part of one pass across the remaining revision-workflow tasks.

## 2026-09-12 — Document section types and the revision workflow

- Implemented directly by Claude as part of one pass across the remaining revision-workflow tasks.

## 2026-09-12 — Make a programme a task that lists other tasks

- Implemented directly by Claude as part of one pass across the remaining revision-workflow tasks.

## 2026-09-12 — Add TaskState FSM, complete.py, and deprecate.py

- Closed retrospectively. The work landed on 2026-06-13 in commit 8a9de33 (PR #10) but the task file was never moved out of pending, so it has appeared in every listing since. All four acceptance criteria verified as still holding: the suite passes, complete.py and deprecate.py both move tasks and set status correctly, and an invalid transition such as completed to pending raises ValueError.

## 2026-09-12 — Task failure state

- Programme complete. Delivered the failed state, typed sections (Failure and Revision discriminated on type), record-failure and record-revision, latest_section and completed_by_section, and sub_tasks making a programme an ordinary task. Also migrated this file itself from the hand-authored programme shape, which the Task model could not parse and which made main.py show raise on the whole pending directory.
