# Add TaskState FSM, complete.py, and deprecate.py

**Created:** 2026-06-13 13:46:14
**Model:** claude-sonnet-4-6 — implementing locally
**Agent:** `local`
**Status:** planned

## Goal

Task lifecycle transitions are enforced by a Python FSM; completing and deprecating tasks use scripts, not natural language instructions.

## Background

Tasks currently have a plain string status field. Completion and deprecation are described only in natural language in command.md. This adds a typed FSM so transitions are validated in code.

## Changes

- scripts/workflow.py (new) — TaskState enum, TRANSITIONS dict, transition() function
- scripts/task.py — status field typed as TaskState; default changed from planned to pending
- scripts/complete.py (new) — CLI: validates transition to completed, writes Results, moves file, appends to development-log.md
- scripts/deprecate.py (new) — CLI: validates transition to deprecated, writes Deprecated-by, moves file, appends to development-log.md
- command.md — update completion and deprecation sections to reference scripts
- tests/test_workflow.py (new) — FSM transition validation tests
- tests/test_complete.py (new) — complete.py round-trip tests
- tests/test_deprecate.py (new) — deprecate.py round-trip tests

## Files to read before starting

- scripts/task.py
- scripts/create.py
- tests/test_task.py
- tests/test_create.py
- command.md

## Recommended approach

1. Write workflow.py with TaskState and transition(). 2. Update task.py status field. 3. Write complete.py. 4. Write deprecate.py. 5. Write tests. 6. Update command.md.

## Done when

- [ ] uv run pytest passes with all new tests green
- [ ] uv run python scripts/complete.py on a pending task moves it to tasks/completed/ with status completed
- [ ] uv run python scripts/deprecate.py on a pending task moves it to tasks/deprecated/ with status deprecated
- [ ] Invalid transitions (e.g. completed -> pending) raise and exit non-zero

## Pre-flight ⏳ L1

- Spec: 507 tokens
- Files: task.py (620), create.py (1,152), test_task.py (1,176), test_create.py (939), command.md (3,839) → 7,726 total
- Reasoning buffer: 12,000 (estimated)
- Estimated total: ~20,233 tokens
- Complexity: L1 — fits comfortably — well within context window


## Results
<!-- Filled in by the executing model after completion -->
**Tests:**
**Files changed:**
**Summary:**
