from datetime import date
from unittest.mock import patch

from show import closed_summary, parse_task, print_table
from task import ExecutionMode, Task, to_toml


def _write_task(path, created: str, title: str = 'A task') -> None:
    task = Task.model_validate({
        'title': title, 'goal': 'g', 'model': 'claude-sonnet', 'agent': 'a',
        'status': 'completed', 'created': created,
    })
    path.write_text(to_toml(task))


# ── parse_task / print_table (execution mode) ──────────────────────────────────

def test_parse_task_includes_mode(tmp_path):
    path = tmp_path / 'task.toml'
    task = Task.model_validate({
        'title': 'A task', 'goal': 'g', 'model': 'm', 'agent': 'a',
        'execution_mode': 'local_worktree',
    })
    path.write_text(to_toml(task))
    assert parse_task(path)['mode'] == ExecutionMode.local_worktree


def test_print_table_shows_mode_column(capsys):
    tasks = [{'title': 'A task', 'status': 'in_progress', 'created': '2026-01-01', 'model': 'm', 'mode': 'local_worktree'}]
    print_table(tasks, 'pending', page=1, per_page=20, total=1)
    out = capsys.readouterr().out
    assert 'Mode' in out
    assert 'local_worktree' in out


# ── closed_summary ────────────────────────────────────────────────────────────

def test_empty_when_no_closed_tasks(tmp_path):
    (tmp_path / 'tasks' / 'completed').mkdir(parents=True)
    (tmp_path / 'tasks' / 'deprecated').mkdir(parents=True)
    assert closed_summary(tmp_path) == ''


def test_empty_when_directories_missing(tmp_path):
    assert closed_summary(tmp_path) == ''


def test_counts_completed_tasks(tmp_path):
    d = tmp_path / 'tasks' / 'completed'
    d.mkdir(parents=True)
    _write_task(d / '2026-01-01T00-00-00-alpha.toml', '2026-01-01')
    _write_task(d / '2026-02-01T00-00-00-beta.toml', '2026-02-01')
    result = closed_summary(tmp_path)
    assert '2 completed' in result


def test_counts_deprecated_tasks(tmp_path):
    d = tmp_path / 'tasks' / 'deprecated'
    d.mkdir(parents=True)
    _write_task(d / '2026-03-01T00-00-00-gamma.toml', '2026-03-01')
    result = closed_summary(tmp_path)
    assert '1 deprecated' in result


def test_counts_both_buckets(tmp_path):
    comp = tmp_path / 'tasks' / 'completed'
    comp.mkdir(parents=True)
    _write_task(comp / '2026-01-10T00-00-00-a.toml', '2026-01-10')

    dep = tmp_path / 'tasks' / 'deprecated'
    dep.mkdir(parents=True)
    _write_task(dep / '2026-02-10T00-00-00-b.toml', '2026-02-10')

    result = closed_summary(tmp_path)
    assert '1 completed' in result
    assert '1 deprecated' in result


def test_span_in_days_uses_earliest_date(tmp_path):
    d = tmp_path / 'tasks' / 'completed'
    d.mkdir(parents=True)
    earliest = date(2026, 1, 1)
    _write_task(d / '2026-01-01T00-00-00-a.toml', '2026-01-01')
    _write_task(d / '2026-03-01T00-00-00-b.toml', '2026-03-01')

    today = date(2026, 6, 12)
    with patch('show.date') as mock_date:
        mock_date.today.return_value = today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = closed_summary(tmp_path)

    expected_days = (today - earliest).days
    assert f'{expected_days} days' in result
    assert '2026-01-01' in result


def test_omits_span_when_no_parseable_dates(tmp_path):
    d = tmp_path / 'tasks' / 'completed'
    d.mkdir(parents=True)
    _write_task(d / 'no-date.toml', created='')
    result = closed_summary(tmp_path)
    assert 'completed' in result
    assert 'days' not in result


def test_no_deprecated_label_when_none_exist(tmp_path):
    d = tmp_path / 'tasks' / 'completed'
    d.mkdir(parents=True)
    _write_task(d / '2026-01-01T00-00-00-a.toml', '2026-01-01')
    result = closed_summary(tmp_path)
    assert 'deprecated' not in result


def test_no_completed_label_when_none_exist(tmp_path):
    d = tmp_path / 'tasks' / 'deprecated'
    d.mkdir(parents=True)
    _write_task(d / '2026-01-01T00-00-00-a.toml', '2026-01-01')
    result = closed_summary(tmp_path)
    assert 'completed' not in result
    assert '1 deprecated' in result
