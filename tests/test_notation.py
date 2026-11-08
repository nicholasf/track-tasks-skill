import json
import subprocess
import sys
from pathlib import Path

import pytest

import hooks
import hooks_install
import notation
from task import Task, to_toml

MAIN = Path(__file__).resolve().parents[1] / 'scripts' / 'main.py'


def _write(root: Path, bucket: str, stem: str, **fields) -> Path:
    """Write a task file into root/tasks/<bucket>/<stem>.toml."""
    task = Task.model_validate({'title': 'A task', 'goal': 'The goal.', 'model': 'm', 'agent': 'a', **fields})
    path = root / 'tasks' / bucket / f'{stem}.toml'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_toml(task))
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project with one pending, one in-progress and one completed task."""
    _write(tmp_path, 'pending', '2026-09-27T09-10-33-add-notation', title='Add notation',
           short_code='20260927091033', branch='feature/skill-notation', done_when=['tests pass', 'docs'])
    _write(tmp_path, 'pending', '2026-09-28T10-00-00-wire-hooks', title='Wire hooks',
           short_code='20260928100000', status='in_progress')
    _write(tmp_path, 'completed', '2026-09-12T08-43-32-old-task', title='Old task', status='completed',
           results={'summary': 'Did it.', 'tests': 'pass', 'files_changed': 'x'})
    return tmp_path


# ── Finding notations ────────────────────────────────────────────────────────

def test_find_notations_bare_key_and_payload():
    assert notation.find_notations('^task and ^task:abc', '^task') == [('^task', ''), ('^task:abc', 'abc')]


def test_find_notations_needs_whitespace_before():
    assert notation.find_notations('x^task:abc', '^task') == []


def test_find_notations_key_must_not_run_on():
    assert notation.find_notations('^tasks ^task-x', '^task') == []


def test_find_notations_strips_trailing_punctuation():
    assert notation.find_notations('is ^task:abc done?', '^task') == [('^task:abc', 'abc')]


def test_find_notations_decodes_payload():
    assert notation.find_notations('^task:a+b%2Fc', '^task') == [('^task:a+b%2Fc', 'a b/c')]


def test_find_notations_drops_duplicates():
    assert notation.find_notations('^task:a then ^task:a', '^task') == [('^task:a', 'a')]


def test_find_notations_other_skill_key_is_ignored():
    assert notation.find_notations('^top:pond', '^task') == []


# ── Front matter ─────────────────────────────────────────────────────────────

def test_skill_md_declares_task_key():
    assert notation.read_notation_key() == '^task'
    assert notation.read_skill_name() == 'track-tasks'


def test_read_notation_key_defaults_when_missing(tmp_path):
    skill_md = tmp_path / 'SKILL.md'
    skill_md.write_text('---\nname: x\n---\nbody\n')
    assert notation.read_notation_key(skill_md) == notation.DEFAULT_KEY


# ── Resolving ────────────────────────────────────────────────────────────────

def test_load_tasks_skips_unparseable(project):
    (project / 'tasks' / 'pending' / 'broken.toml').write_text('not = [valid')
    assert len(notation.load_tasks(project)) == 3


def test_expand_by_short_code(project):
    tag, kind, text = notation.expand('20260927091033', project, notation.load_tasks(project))
    assert (tag, kind) == ('expanded', 'task')
    assert 'Task 20260927091033: Add notation' in text
    assert 'File: tasks/pending/2026-09-27T09-10-33-add-notation.toml' in text
    assert 'Branch: feature/skill-notation' in text
    assert 'Done when: tests pass; docs' in text


def test_expand_by_slug_is_case_insensitive(project):
    tag, _, text = notation.expand('Wire-Hooks', project, notation.load_tasks(project))
    assert tag == 'expanded'
    assert 'Status: in_progress' in text


def test_expand_task_without_short_code_uses_slug(project):
    _, _, text = notation.expand('old-task', project, notation.load_tasks(project))
    assert text.startswith('Task old-task: Old task')
    assert 'Result: Did it.' in text


def test_expand_counts_failures_without_their_outcome(project):
    _write(project, 'pending', '2026-10-01T00-00-00-flaky', title='Flaky',
           sections={'1': {'type': 'failure', 'outcome': 'secret outcome', 'log': 'long log'}})
    _, _, text = notation.expand('flaky', project, notation.load_tasks(project))
    assert 'Failed attempts: 1' in text
    assert 'secret outcome' not in text


def test_expand_programme_lists_sub_tasks(project):
    _write(project, 'pending', '2026-10-01T00-00-00-programme', title='Programme',
           sub_tasks=[{'slug': 'a', 'done': True}, {'slug': 'b'}])
    _, _, text = notation.expand('programme', project, notation.load_tasks(project))
    assert 'Programme: 1/2 sub-tasks done: a (done), b (not done)' in text


def test_expand_empty_payload_lists_pending_and_in_progress(project):
    tag, kind, text = notation.expand('', project, notation.load_tasks(project))
    assert (tag, kind) == ('expanded', 'summary')
    assert 'Add notation' in text and 'Wire hooks' in text
    assert 'Old task' not in text


def test_expand_bucket(project):
    tag, kind, text = notation.expand('completed', project, notation.load_tasks(project))
    assert (tag, kind) == ('expanded', 'bucket')
    assert text.startswith('Completed tasks (1):')
    assert 'old-task  [completed]  Old task' in text


def test_expand_empty_bucket(project):
    _, _, text = notation.expand('deprecated', project, notation.load_tasks(project))
    assert text == 'Deprecated tasks: none.'


def test_expand_listing_is_capped(tmp_path):
    for i in range(notation.DEFAULT_LISTED + 5):
        _write(tmp_path, 'completed', f'2026-01-01T00-00-{i:02d}-t{i:02d}', status='completed')
    _, _, text = notation.expand('completed', tmp_path, notation.load_tasks(tmp_path))
    assert '… 5 older not shown.' in text
    assert 't24' in text and 't00' not in text


def test_expand_bucket_with_count(tmp_path):
    for i in range(40):
        _write(tmp_path, 'completed', f'2026-01-01T00-00-{i:02d}-t{i:02d}', status='completed')
    tag, _, text = notation.expand('completed:33', tmp_path, notation.load_tasks(tmp_path))
    assert tag == 'expanded'
    assert text.count('[completed]') == 33
    assert '… 7 older not shown.' in text
    assert 't39' in text and 't07' in text and 't06' not in text


def test_expand_bucket_count_above_total_lists_all(project):
    _, _, text = notation.expand('completed:50', project, notation.load_tasks(project))
    assert text.count('[completed]') == 1
    assert 'older not shown' not in text


@pytest.mark.parametrize('count', ['0', 'abc', '-3', '2.5'])
def test_expand_bucket_bad_count_is_an_error(project, count):
    tag, kind, text = notation.expand(f'completed:{count}', project, notation.load_tasks(project))
    assert (tag, kind) == ('error', 'count')
    assert f"'{count}' is not a count" in text


def test_find_and_expand_bucket_count_from_prompt(project):
    out = notation.expand_prompt('show me ^task:Completed:5.', project)
    assert '<notation>^task:Completed:5</notation>' in out
    assert 'Completed tasks (1):' in out


def test_legend_mentions_count():
    assert '[:count]' in notation.legend('^task')


def test_expand_unknown_handle_suggests_partial_slug(project):
    tag, kind, text = notation.expand('add', project, notation.load_tasks(project))
    assert (tag, kind) == ('error', 'unknown')
    assert "Unknown handle 'add'" in text
    assert 'Did you mean: add-notation' in text


def test_expand_unknown_handle_suggests_close_bucket(project):
    _, _, text = notation.expand('complted', project, notation.load_tasks(project))
    assert 'Did you mean: completed?' in text


def test_expand_without_tasks_directory(tmp_path):
    tag, _, text = notation.expand('x', tmp_path, [])
    assert tag == 'error'
    assert 'No tasks/ directory' in text


# ── Expanded forms ───────────────────────────────────────────────────────────

def test_build_expanded_form_escapes_and_indents():
    form = notation.build_expanded_form('^task:a&b', 'error', 'bad <x>\nline two', 'track-tasks')
    assert form == (
        '<skill-notation skill="track-tasks">\n'
        '  <notation>^task:a&amp;b</notation>\n'
        '  <error>\n'
        '    bad &lt;x&gt;\n'
        '    line two\n'
        '  </error>\n'
        '</skill-notation>'
    )


def test_expand_prompt_one_block_per_notation_in_order(project):
    out = notation.expand_prompt('compare ^task:wire-hooks with ^task:20260927091033', project)
    assert out.count('<skill-notation skill="track-tasks">') == 2
    assert out.index('^task:wire-hooks') < out.index('^task:20260927091033')


def test_expand_prompt_without_notations_is_empty(project):
    assert notation.expand_prompt('what tasks are pending?', project) == ''


# ── Completion ───────────────────────────────────────────────────────────────

def test_completion_lists_buckets_then_newest_tasks(project):
    values = [h['value'] for h in notation.build_completion(project)['handles']]
    assert values[:4] == list(notation.BUCKETS)
    assert values[4:6] == ['20260928100000', 'wire-hooks']
    assert 'old-task' in values


def test_completion_header(project):
    completion = notation.build_completion(project)
    assert completion['key'] == '^task'
    assert completion['skill'] == 'track-tasks'


# ── Hooks ────────────────────────────────────────────────────────────────────

def test_hook_session_start_prints_legend_in_task_projects(project):
    assert hooks.run('session-start', 'text', '', str(project)).startswith('Notation: ^task or ^task:<')


def test_hook_session_start_silent_without_tasks(tmp_path):
    assert hooks.run('session-start', 'text', '', str(tmp_path)) == ''


def test_hook_prompt_claude_format_uses_harness_cwd(project):
    stdin = json.dumps({'prompt': 'look at ^task:wire-hooks', 'cwd': str(project)})
    out = json.loads(hooks.run('prompt', 'claude', stdin, None))
    assert out['hookSpecificOutput']['hookEventName'] == 'UserPromptSubmit'
    assert 'Task 20260928100000: Wire hooks' in out['hookSpecificOutput']['additionalContext']


def test_hook_prompt_without_notation_prints_nothing(project):
    stdin = json.dumps({'prompt': 'hello', 'cwd': str(project)})
    assert hooks.run('prompt', 'claude', stdin, None) == ''


def test_hook_never_fails_loudly(project):
    result = subprocess.run(
        [sys.executable, str(MAIN), 'hook', 'prompt', '--format', 'claude'],
        input='not json', capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stdout == ''
    assert 'track-tasks hook prompt' in result.stderr


def test_cli_hook_prompt_text(project):
    result = subprocess.run(
        [sys.executable, str(MAIN), 'hook', 'prompt', '--cwd', str(project)],
        input='^task:old-task', capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert 'Task old-task: Old task' in result.stdout


def test_cli_notation_complete(project):
    result = subprocess.run(
        [sys.executable, str(MAIN), 'notation', 'complete', '--cwd', str(project)],
        capture_output=True, text=True,
    )
    assert json.loads(result.stdout)['key'] == '^task'


# ── Hook installer ───────────────────────────────────────────────────────────

def test_install_claude_is_idempotent_and_keeps_other_hooks(tmp_path):
    path = tmp_path / 'settings.json'
    other = {'hooks': [{'type': 'command', 'command': 'topology.cli hook prompt --format claude'}]}
    path.write_text(json.dumps({'model': 'opus', 'hooks': {'UserPromptSubmit': [other]}}))
    hooks_install.install('claude', path)
    hooks_install.install('claude', path)
    settings = json.loads(path.read_text())
    assert settings['model'] == 'opus'
    assert len(settings['hooks']['UserPromptSubmit']) == 2
    assert len(settings['hooks']['SessionStart']) == 1
    assert hooks_install.is_installed('claude', path)
    assert (tmp_path / 'settings.json.track-tasks-backup').exists()


def test_uninstall_claude_removes_only_ours(tmp_path):
    path = tmp_path / 'settings.json'
    other = {'hooks': [{'type': 'command', 'command': 'other'}]}
    path.write_text(json.dumps({'hooks': {'UserPromptSubmit': [other]}}))
    hooks_install.install('claude', path)
    hooks_install.uninstall('claude', path)
    assert json.loads(path.read_text()) == {'hooks': {'UserPromptSubmit': [other]}}
    assert not hooks_install.is_installed('claude', path)


def test_claude_hook_commands_call_main_py():
    entries = hooks_install.claude_hook_entries()
    command = entries['UserPromptSubmit']['hooks'][0]['command']
    assert command.endswith('track-tasks-skill/scripts/main.py" hook prompt --format claude')
    assert '.venv/bin/python3' in command


def test_install_pi_symlinks_extension(tmp_path):
    path = tmp_path / 'extensions' / 'track-tasks.ts'
    hooks_install.install('pi', path)
    assert path.resolve() == hooks_install.PI_EXTENSION_SOURCE
    assert hooks_install.PI_EXTENSION_SOURCE.exists()
    hooks_install.uninstall('pi', path)
    assert not path.exists()


def test_install_pi_refuses_to_replace_a_real_file(tmp_path):
    path = tmp_path / 'track-tasks.ts'
    path.write_text('mine')
    with pytest.raises(FileExistsError):
        hooks_install.install('pi', path)
