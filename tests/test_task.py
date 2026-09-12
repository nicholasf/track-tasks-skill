import pytest
from task import ExecutionMode, Failure, Revision, Section, Task, from_toml, render, to_toml


def _minimal() -> dict:
    return {'title': 'Do a thing', 'goal': 'The thing is done.', 'model': 'qwen3-coder-30b', 'agent': 'pond-qwen-hermes'}


# ── Task model ────────────────────────────────────────────────────────────────

def test_task_requires_title():
    with pytest.raises(Exception):
        Task.model_validate({'goal': 'g', 'model': 'm', 'agent': 'a'})


def test_task_requires_goal():
    with pytest.raises(Exception):
        Task.model_validate({'title': 't', 'model': 'm', 'agent': 'a'})


def test_task_requires_model():
    with pytest.raises(Exception):
        Task.model_validate({'title': 't', 'goal': 'g', 'agent': 'a'})


def test_task_requires_agent():
    with pytest.raises(Exception):
        Task.model_validate({'title': 't', 'goal': 'g', 'model': 'm'})


def test_task_defaults():
    task = Task.model_validate(_minimal())
    assert task.status == 'pending'
    assert task.background == ''
    assert task.changes == []
    assert task.files_to_read == []
    assert task.open_questions == []
    assert task.recommended_approach == ''
    assert task.done_when == []
    assert task.preflight == ''
    assert task.execution_mode == ExecutionMode.local
    assert task.worktree_path == ''
    assert task.worktree_branch == ''


# ── render structure ──────────────────────────────────────────────────────────

def test_render_title_as_h1():
    task = Task.model_validate(_minimal())
    assert render(task).startswith('# Do a thing')


def test_render_contains_model_field():
    task = Task.model_validate(_minimal())
    assert '**Model:** qwen3-coder-30b' in render(task)


def test_render_agent_in_backticks():
    task = Task.model_validate(_minimal())
    assert '**Agent:** `pond-qwen-hermes`' in render(task)


def test_render_contains_goal_section():
    task = Task.model_validate(_minimal())
    assert '## Goal' in render(task)
    assert 'The thing is done.' in render(task)


def test_render_omits_background_when_empty():
    task = Task.model_validate(_minimal())
    assert '## Background' not in render(task)


def test_render_includes_background_when_set():
    task = Task.model_validate({**_minimal(), 'background': 'Some context.'})
    assert '## Background' in render(task)
    assert 'Some context.' in render(task)


def test_render_omits_changes_when_empty():
    task = Task.model_validate(_minimal())
    assert '## Changes' not in render(task)


def test_render_includes_changes_as_list():
    task = Task.model_validate({**_minimal(), 'changes': ['Add foo.py', 'Remove bar.py']})
    output = render(task)
    assert '## Changes' in output
    assert '- Add foo.py' in output
    assert '- Remove bar.py' in output


def test_render_omits_files_to_read_when_empty():
    task = Task.model_validate(_minimal())
    assert '## Files to read before starting' not in render(task)


def test_render_includes_files_to_read():
    task = Task.model_validate({**_minimal(), 'files_to_read': ['src/main.py']})
    output = render(task)
    assert '## Files to read before starting' in output
    assert '- src/main.py' in output


def test_render_omits_open_questions_when_empty():
    task = Task.model_validate(_minimal())
    assert '## Open questions' not in render(task)


def test_render_omits_recommended_approach_when_empty():
    task = Task.model_validate(_minimal())
    assert '## Recommended approach' not in render(task)


def test_render_done_when_uses_checkbox():
    task = Task.model_validate({**_minimal(), 'done_when': ['Tests pass', 'No type errors']})
    output = render(task)
    assert '- [ ] Tests pass' in output
    assert '- [ ] No type errors' in output


def test_render_always_includes_results_section():
    task = Task.model_validate(_minimal())
    assert '## Results' in render(task)
    assert '**Tests:**' in render(task)


# ── preflight rendering ───────────────────────────────────────────────────────

def test_render_preflight_placeholder_when_empty():
    task = Task.model_validate(_minimal())
    output = render(task)
    assert '## Pre-flight' in output
    assert 'not yet computed' in output


def test_render_preflight_unavailable_via_remote():
    task = Task.model_validate({**_minimal(), 'preflight': 'unavailable-via-remote'})
    output = render(task)
    assert '## Pre-flight' in output
    assert 'remote tokenizer could not be reached' in output


def test_render_preflight_unavailable_via_local():
    task = Task.model_validate({**_minimal(), 'preflight': 'unavailable-via-local'})
    output = render(task)
    assert '## Pre-flight' in output
    assert 'local tokenizer failed' in output


def test_render_preflight_content_embedded_directly():
    preflight_text = '## Pre-flight ⏳ L1\n\n- Spec: 500 tokens\n'
    task = Task.model_validate({**_minimal(), 'preflight': preflight_text})
    output = render(task)
    assert '## Pre-flight ⏳ L1' in output
    assert '- Spec: 500 tokens' in output
    assert output.count('## Pre-flight') == 1


# ── TOML round-trip ───────────────────────────────────────────────────────────

def test_to_toml_from_toml_roundtrip_minimal():
    task = Task.model_validate(_minimal())
    assert from_toml(to_toml(task)) == task


def test_to_toml_from_toml_roundtrip_full():
    task = Task.model_validate({
        **_minimal(),
        'created': '2026-01-01 00:00:00',
        'background': 'Some context.',
        'changes': ['Add foo.py', 'Remove bar.py'],
        'files_to_read': ['src/main.py'],
        'open_questions': ['Is this right?'],
        'recommended_approach': 'Do it carefully.',
        'done_when': ['Tests pass'],
        'preflight': '## Pre-flight ⏳ L1\n\n- Spec: 500 tokens\n',
    })
    assert from_toml(to_toml(task)) == task


def test_to_toml_roundtrip_with_results():
    task = Task.model_validate({
        **_minimal(),
        'results': {'tests': 'pass', 'files_changed': 'foo.py', 'summary': 'Did the thing.'},
    })
    assert from_toml(to_toml(task)) == task


def test_to_toml_roundtrip_status_enum():
    task = Task.model_validate({**_minimal(), 'status': 'completed'})
    roundtripped = from_toml(to_toml(task))
    assert roundtripped.status == 'completed'
    assert roundtripped == task


def test_to_toml_roundtrip_execution_mode_and_worktree_fields():
    task = Task.model_validate({
        **_minimal(),
        'execution_mode': 'local_worktree',
        'worktree_path': '../wt-add-logging',
        'worktree_branch': 'task/add-logging',
    })
    roundtripped = from_toml(to_toml(task))
    assert roundtripped.execution_mode == ExecutionMode.local_worktree
    assert roundtripped.worktree_path == '../wt-add-logging'
    assert roundtripped.worktree_branch == 'task/add-logging'
    assert roundtripped == task


def test_to_toml_omits_results_table_when_empty():
    task = Task.model_validate(_minimal())
    assert '[results]' not in to_toml(task)


def test_to_toml_escapes_quotes_and_backslashes():
    task = Task.model_validate({**_minimal(), 'background': 'say "hi" \\ bye'})
    assert from_toml(to_toml(task)).background == 'say "hi" \\ bye'


# ── sections ──────────────────────────────────────────────────────────────────

def _section_payload() -> dict:
    return {
        'type': 'failure',
        'at_utc': '2026-09-12T08:44:48Z',
        'at_local': '2026-09-12 04:44:48 EDT',
        'agent': 'pond-qwen',
        'model': 'qwen3.8-27b',
        'complexity': 'L1 ~13,938',
        'outcome': 'Tests failed: 2 errors',
        'log': 'Traceback (most recent call last):\n  File "x.py", line 1\nAssertionError: boom',
    }


def test_sections_default_to_empty():
    task = Task.model_validate(_minimal())
    assert task.sections == {}


def test_render_excludes_sections():
    task = Task.model_validate({
        **_minimal(),
        'sections': {'1': _section_payload()},
    })
    output = render(task)
    assert 'failure' not in output
    assert '2026-09-12T08:44:48Z' not in output
    assert '2026-09-12 04:44:48 EDT' not in output
    assert 'L1 ~13,938' not in output
    assert 'Tests failed: 2 errors' not in output
    assert 'AssertionError: boom' not in output
    assert 'Traceback' not in output
    assert '## Sections' not in output


def test_to_toml_uses_numbered_section_headers():
    task = Task.model_validate({
        **_minimal(),
        'sections': {'1': _section_payload(), '2': _section_payload()},
    })
    text = to_toml(task)
    assert '[sections.1]' in text
    assert '[sections.2]' in text


def test_to_toml_omits_sections_table_when_empty():
    task = Task.model_validate(_minimal())
    assert '[sections' not in to_toml(task)


def test_to_toml_from_toml_roundtrip_with_sections():
    task = Task.model_validate({
        **_minimal(),
        'sections': {'1': _section_payload(), '2': _section_payload()},
    })
    assert from_toml(to_toml(task)) == task


# ── Failure and Revision section classes ──────────────────────────────────────

def test_failure_defaults_type():
    assert Failure().type == 'failure'


def test_revision_defaults_type_and_instructions():
    revision = Revision()
    assert revision.type == 'revision'
    assert revision.instructions == ''


# ── section types ─────────────────────────────────────────────────────────────

def test_failure_round_trips_as_a_failure():
    # Without a discriminator this silently returns a bare Section and loses log.
    t = Task.model_validate(_minimal() | {
        'sections': {'1': Failure(agent='pond', log='detail', outcome='stopped')},
    })
    back = from_toml(to_toml(t))
    assert isinstance(back.sections['1'], Failure)
    assert back.sections['1'].log == 'detail'


def test_revision_round_trips_as_a_revision():
    t = Task.model_validate(_minimal() | {
        'sections': {'1': Revision(agent='claude', instructions='do it differently')},
    })
    back = from_toml(to_toml(t))
    assert isinstance(back.sections['1'], Revision)
    assert back.sections['1'].instructions == 'do it differently'


def test_mixed_sections_each_keep_their_type():
    t = Task.model_validate(_minimal() | {
        'sections': {'1': Failure(log='why'), '2': Revision(instructions='fix')},
    })
    back = from_toml(to_toml(t))
    assert isinstance(back.sections['1'], Failure)
    assert isinstance(back.sections['2'], Revision)


def test_section_base_has_only_universal_fields():
    assert set(Section.model_fields) == {'type', 'at_utc', 'at_local'}


# ── rendering revisions ───────────────────────────────────────────────────────

def test_render_includes_the_latest_revision():
    t = Task.model_validate(_minimal() | {'sections': {'1': Revision(instructions='CORRECTION')}})
    assert 'CORRECTION' in render(t)


def test_render_shows_only_the_latest_revision():
    t = Task.model_validate(_minimal() | {'sections': {
        '1': Revision(instructions='FIRST'),
        '2': Revision(instructions='SECOND'),
    }})
    out = render(t)
    assert 'SECOND' in out
    assert 'FIRST' not in out


def test_render_orders_revisions_numerically_not_lexically():
    # '10' must beat '9' — string comparison would pick 9.
    t = Task.model_validate(_minimal() | {'sections': {
        '9': Revision(instructions='NINE'),
        '10': Revision(instructions='TEN'),
    }})
    out = render(t)
    assert 'TEN' in out
    assert 'NINE' not in out


def test_render_never_shows_failure_content():
    t = Task.model_validate(_minimal() | {'sections': {
        '1': Failure(outcome='OUTCOME', log='LOG', complexity='COMPLEXITY'),
        '2': Revision(instructions='SHOWN'),
    }})
    out = render(t)
    assert 'SHOWN' in out
    for hidden in ('OUTCOME', 'LOG', 'COMPLEXITY'):
        assert hidden not in out


def test_render_omits_revision_heading_when_none():
    assert '## Revision' not in render(Task.model_validate(_minimal()))


# ── header fields ─────────────────────────────────────────────────────────────

def test_latest_section_and_completed_by_section_are_not_rendered():
    t = Task.model_validate(_minimal() | {'latest_section': '7', 'completed_by_section': '7'})
    out = render(t)
    assert 'latest_section' not in out
    assert 'completed_by_section' not in out


def test_sub_tasks_default_empty_and_round_trip():
    assert Task.model_validate(_minimal()).sub_tasks == []
    t = Task.model_validate(_minimal() | {'sub_tasks': ['a.toml', 'b.toml']})
    assert from_toml(to_toml(t)).sub_tasks == ['a.toml', 'b.toml']


def test_sub_tasks_are_not_rendered():
    t = Task.model_validate(_minimal() | {'sub_tasks': ['secret-plan.toml']})
    assert 'secret-plan.toml' not in render(t)
