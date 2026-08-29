import pytest
from task import Task, from_toml, render, to_toml


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


def test_to_toml_omits_results_table_when_empty():
    task = Task.model_validate(_minimal())
    assert '[results]' not in to_toml(task)


def test_to_toml_escapes_quotes_and_backslashes():
    task = Task.model_validate({**_minimal(), 'background': 'say "hi" \\ bye'})
    assert from_toml(to_toml(task)).background == 'say "hi" \\ bye'
