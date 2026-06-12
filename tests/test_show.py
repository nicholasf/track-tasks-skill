import re
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from show import closed_summary


def _write_task(path, created: str, title: str = 'A task') -> None:
    path.write_text(
        f'# {title}\n\n**Status:** completed\n**Created:** {created}\n**Model:** claude-sonnet\n'
    )


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
    _write_task(d / '2026-01-01T00-00-00-alpha.md', '2026-01-01')
    _write_task(d / '2026-02-01T00-00-00-beta.md', '2026-02-01')
    result = closed_summary(tmp_path)
    assert '2 completed' in result


def test_counts_deprecated_tasks(tmp_path):
    d = tmp_path / 'tasks' / 'deprecated'
    d.mkdir(parents=True)
    _write_task(d / '2026-03-01T00-00-00-gamma.md', '2026-03-01')
    result = closed_summary(tmp_path)
    assert '1 deprecated' in result


def test_counts_both_buckets(tmp_path):
    comp = tmp_path / 'tasks' / 'completed'
    comp.mkdir(parents=True)
    _write_task(comp / '2026-01-10T00-00-00-a.md', '2026-01-10')

    dep = tmp_path / 'tasks' / 'deprecated'
    dep.mkdir(parents=True)
    _write_task(dep / '2026-02-10T00-00-00-b.md', '2026-02-10')

    result = closed_summary(tmp_path)
    assert '1 completed' in result
    assert '1 deprecated' in result


def test_span_in_days_uses_earliest_date(tmp_path):
    d = tmp_path / 'tasks' / 'completed'
    d.mkdir(parents=True)
    earliest = date(2026, 1, 1)
    _write_task(d / '2026-01-01T00-00-00-a.md', '2026-01-01')
    _write_task(d / '2026-03-01T00-00-00-b.md', '2026-03-01')

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
    (d / 'no-date.md').write_text('# Task\n\n**Status:** completed\n**Model:** x\n')
    result = closed_summary(tmp_path)
    assert 'completed' in result
    assert 'days' not in result


def test_no_deprecated_label_when_none_exist(tmp_path):
    d = tmp_path / 'tasks' / 'completed'
    d.mkdir(parents=True)
    _write_task(d / '2026-01-01T00-00-00-a.md', '2026-01-01')
    result = closed_summary(tmp_path)
    assert 'deprecated' not in result


def test_no_completed_label_when_none_exist(tmp_path):
    d = tmp_path / 'tasks' / 'deprecated'
    d.mkdir(parents=True)
    _write_task(d / '2026-01-01T00-00-00-a.md', '2026-01-01')
    result = closed_summary(tmp_path)
    assert 'completed' not in result
    assert '1 deprecated' in result
