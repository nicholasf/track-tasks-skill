import json
from unittest.mock import MagicMock, patch

import pytest

from estimate_tokens import (
    DEFAULT_REASONING_BUFFER,
    L1_FRACTION,
    L1_THRESHOLD,
    L2_FRACTION,
    L2_THRESHOLD,
    append_token_estimate,
    build_token_estimate_section,
    complexity_level,
    difficulty_rating,
    parse_files_to_read,
    parse_model_field,
    read_topology_context_window,
    read_topology_reasoning_buffer,
    read_topology_tok_s,
    tokenize_llama,
    tokenize_ollama,
)


# ── parse_model_field ─────────────────────────────────────────────────────────

def test_parse_model_field_extracts_value():
    text = '**Model:** pond-qwen-hermes — mechanical rename\n'
    assert parse_model_field(text) == 'pond-qwen-hermes — mechanical rename'


def test_parse_model_field_returns_none_when_absent():
    assert parse_model_field('# Task\n\nNo model field here.\n') is None


def test_parse_model_field_trims_whitespace():
    text = '**Model:**   qwen3-coder-30b   \n'
    assert parse_model_field(text) == 'qwen3-coder-30b'


# ── parse_files_to_read ───────────────────────────────────────────────────────

TASK_WITH_FILES = """\
# My Task

**Model:** pond-qwen-hermes

## Files to read before starting
- src/schema.sql
- migrations/000001.up.sql
- README.md

## Goal
Do the thing.
"""

TASK_NO_FILES_SECTION = """\
# My Task

**Model:** pond-qwen-hermes

## Goal
Do the thing.
"""


def test_parse_files_to_read_extracts_paths():
    paths = parse_files_to_read(TASK_WITH_FILES)
    assert paths == ['src/schema.sql', 'migrations/000001.up.sql', 'README.md']


def test_parse_files_to_read_empty_when_section_absent():
    assert parse_files_to_read(TASK_NO_FILES_SECTION) == []


def test_parse_files_to_read_empty_when_section_empty():
    text = '## Files to read before starting\n\n## Goal\n'
    assert parse_files_to_read(text) == []


# ── complexity_level ──────────────────────────────────────────────────────────

def test_complexity_l1_below_threshold():
    assert complexity_level(L1_THRESHOLD - 1) == 'L1'


def test_complexity_l1_at_zero():
    assert complexity_level(0) == 'L1'


def test_complexity_l2_at_lower_bound():
    assert complexity_level(L1_THRESHOLD) == 'L2'


def test_complexity_l2_at_upper_bound():
    assert complexity_level(L2_THRESHOLD) == 'L2'


def test_complexity_l3_above_threshold():
    assert complexity_level(L2_THRESHOLD + 1) == 'L3'


# With context_window — thresholds are relative to context size
def test_complexity_l1_relative_to_context_window():
    ctx = 65536
    just_under_l1 = int(ctx * L1_FRACTION) - 1
    assert complexity_level(just_under_l1, context_window=ctx) == 'L1'


def test_complexity_l2_relative_to_context_window():
    ctx = 65536
    at_l1 = int(ctx * L1_FRACTION)
    assert complexity_level(at_l1, context_window=ctx) == 'L2'


def test_complexity_l3_relative_to_context_window():
    ctx = 65536
    over_l2 = int(ctx * L2_FRACTION) + 1
    assert complexity_level(over_l2, context_window=ctx) == 'L3'


def test_complexity_large_context_window_raises_l3_ceiling():
    # With a 128K context window the L3 threshold is much higher than with fallback
    ctx = 131072
    # 40K is L1 relative to 128K (40K < 40% of 128K = 52K) but L2 with fallback
    assert complexity_level(40_000, context_window=ctx) == 'L1'
    assert complexity_level(40_000) == 'L2'


# ── difficulty_rating ─────────────────────────────────────────────────────────

def test_difficulty_rating_l1_one_hourglass():
    assert difficulty_rating('L1') == '⏳'


def test_difficulty_rating_l2_two_hourglasses():
    assert difficulty_rating('L2') == '⏳⏳'


def test_difficulty_rating_l3_three_hourglasses():
    assert difficulty_rating('L3') == '⏳⏳⏳'


# ── tokenize_llama ────────────────────────────────────────────────────────────

def _mock_urlopen(response_data: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_tokenize_llama_returns_token_count():
    mock_resp = _mock_urlopen({'tokens': [1, 2, 3, 4, 5]})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert tokenize_llama('pond', 'hello world') == 5


def test_tokenize_llama_empty_tokens_returns_zero():
    mock_resp = _mock_urlopen({'tokens': []})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert tokenize_llama('pond', '') == 0


def test_tokenize_llama_returns_none_on_error():
    with patch('urllib.request.urlopen', side_effect=Exception('connection refused')):
        assert tokenize_llama('pond', 'text') is None


# ── tokenize_ollama ───────────────────────────────────────────────────────────

def test_tokenize_ollama_returns_token_count():
    mock_resp = _mock_urlopen({'tokens': [10, 20, 30]})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert tokenize_ollama('gollum', 'qwen3-coder:30b', 'hello') == 3


def test_tokenize_ollama_returns_none_on_error():
    with patch('urllib.request.urlopen', side_effect=OSError('timeout')):
        assert tokenize_ollama('gollum', 'qwen3-coder:30b', 'hello') is None


# ── topology readers ──────────────────────────────────────────────────────────

TOPOLOGY = """\
# Topology

## Model State
*Last updated: 2026-06-08*

| hostname | backend | port | models | context_window | status | last-seen |
|---|---|---|---|---|---|---|
| pond | llama-server | 9337 | qwen3-coder-30b.gguf | 65536 | up | 2026-06-08 |
| gollum | ollama | 11434 | qwen3-coder:30b | 131072 | up | 2026-06-08 |

## Agent State
*Last updated: 2026-06-08*

| hostname | agent | endpoint | status | process | last-seen | reasoning_buffer |
|---|---|---|---|---|---|---|
| pond | hermes | http://pond:8642 | up | running | 2026-06-08 | 12000 |
| gollum | hermes | http://gollum:8642 | down | not found | — | — |

## LLM Benchmarks

| hostname | model | timestamp | ttft_ms | tok_s | runs |
|---|---|---|---|---|---|
| pond | qwen3-coder-30b.gguf | 2026-06-01 | 250 | 215.0 | 3 |
"""


@pytest.fixture
def topology_file(tmp_path):
    p = tmp_path / 'topology.md'
    p.write_text(TOPOLOGY)
    return str(p)


def test_read_context_window_llama_server(topology_file):
    result = read_topology_context_window(topology_file, 'pond', 'llama-server')
    assert result == 65536


def test_read_context_window_ollama(topology_file):
    result = read_topology_context_window(topology_file, 'gollum', 'ollama')
    assert result == 131072


def test_read_context_window_missing_host_returns_none(topology_file):
    assert read_topology_context_window(topology_file, 'unknown', 'llama-server') is None


def test_read_context_window_missing_file_returns_none(tmp_path):
    assert read_topology_context_window(str(tmp_path / 'missing.md'), 'pond', 'llama-server') is None


def test_read_reasoning_buffer_set_value(topology_file):
    assert read_topology_reasoning_buffer(topology_file, 'pond', 'hermes') == 12000


def test_read_reasoning_buffer_dash_falls_back_to_default(topology_file):
    assert read_topology_reasoning_buffer(topology_file, 'gollum', 'hermes') == DEFAULT_REASONING_BUFFER


def test_read_reasoning_buffer_missing_file_returns_default(tmp_path):
    result = read_topology_reasoning_buffer(str(tmp_path / 'missing.md'), 'pond', 'hermes')
    assert result == DEFAULT_REASONING_BUFFER


def test_read_tok_s(topology_file):
    result = read_topology_tok_s(topology_file, 'pond', 'qwen3-coder-30b.gguf')
    assert result == 215.0


def test_read_tok_s_missing_returns_none(topology_file):
    assert read_topology_tok_s(topology_file, 'gollum', 'unknown-model') is None


# ── build_token_estimate_section ───────────────────────────────────────────────────

def test_build_preflight_shows_spec_tokens():
    text = build_token_estimate_section(500, {}, 12000, 65536, 215.0)
    assert '500' in text


def test_build_preflight_shows_file_tokens():
    text = build_token_estimate_section(500, {'schema.sql': 1200}, 12000, 65536, 215.0)
    assert 'schema.sql' in text
    assert '1,200' in text


def test_build_preflight_shows_complexity_level():
    text = build_token_estimate_section(1000, {}, 12000, 65536, 215.0)
    assert 'L1' in text


def test_build_preflight_l3_for_large_task():
    text = build_token_estimate_section(30000, {}, 12000, 65536, 215.0)
    assert 'L3' in text


def test_build_preflight_shows_context_window():
    text = build_token_estimate_section(500, {}, 12000, 65536, 215.0)
    assert '65,536' in text


def test_build_preflight_flags_overflow():
    # estimated_total (40001 + 12000 = 52001) > context_window (65536) - reasoning_buffer (12000) = 53536
    # 52001 < 53536 so fits; test overflow: total > context_window - reasoning_buffer
    text = build_token_estimate_section(55000, {}, 12000, 65536, 215.0)
    assert 'OVERFLOW' in text


def test_build_preflight_shows_time_estimate():
    text = build_token_estimate_section(500, {}, 12000, 65536, 215.0)
    assert 't/s' in text


def test_build_preflight_no_files_shows_none_listed():
    text = build_token_estimate_section(500, {}, 12000, None, None)
    assert 'none listed' in text


def test_build_preflight_no_context_window_omits_window_line():
    text = build_token_estimate_section(500, {}, 12000, None, None)
    assert 'Context window' not in text


def test_build_preflight_no_tok_s_omits_time_line():
    text = build_token_estimate_section(500, {}, 12000, 65536, None)
    assert 'Time estimate' not in text


def test_build_preflight_starts_with_header():
    text = build_token_estimate_section(500, {}, 12000, 65536, 215.0)
    assert text.startswith('## Pre-flight')


def test_build_preflight_header_includes_hourglass_and_level():
    text = build_token_estimate_section(500, {}, 12000, 65536, 215.0)
    first_line = text.splitlines()[0]
    assert '⏳' in first_line
    assert 'L1' in first_line


def test_build_preflight_header_includes_time():
    text = build_token_estimate_section(500, {}, 12000, 65536, 215.0)
    first_line = text.splitlines()[0]
    assert '~' in first_line and 's' in first_line


def test_build_preflight_header_no_time_when_no_tok_s():
    text = build_token_estimate_section(500, {}, 12000, 65536, None)
    first_line = text.splitlines()[0]
    assert first_line == '## Pre-flight ⏳ L1'


def test_build_preflight_l2_two_hourglasses_in_header():
    text = build_token_estimate_section(30000, {}, 0, None, None)
    first_line = text.splitlines()[0]
    assert '⏳⏳' in first_line
    assert 'L2' in first_line


def test_build_preflight_l3_three_hourglasses_in_header():
    text = build_token_estimate_section(50000, {}, 0, None, None)
    first_line = text.splitlines()[0]
    assert '⏳⏳⏳' in first_line
    assert 'L3' in first_line


# ── append_token_estimate ──────────────────────────────────────────────────────────

TASK_TEXT = """\
# My Task

**Model:** pond-qwen-hermes

## Goal
One sentence.

## Done when
- [ ] Tests pass
"""

TASK_WITH_EXISTING_PREFLIGHT = """\
# My Task

**Model:** pond-qwen-hermes

## Goal
One sentence.

## Pre-flight

- Spec: 100 tokens
- Complexity: L1

## Done when
- [ ] Tests pass
"""


def test_append_token_estimate_adds_section(tmp_path):
    task = tmp_path / 'task.md'
    task.write_text(TASK_TEXT)
    append_token_estimate(str(task), '## Pre-flight\n\n- Spec: 100 tokens\n')
    content = task.read_text()
    assert '## Pre-flight' in content
    assert '100 tokens' in content


def test_append_token_estimate_replaces_existing_section(tmp_path):
    task = tmp_path / 'task.md'
    task.write_text(TASK_WITH_EXISTING_PREFLIGHT)
    append_token_estimate(str(task), '## Pre-flight\n\n- Spec: 999 tokens\n')
    content = task.read_text()
    assert '999 tokens' in content
    assert '100 tokens' not in content
    assert content.count('## Pre-flight') == 1


def test_append_token_estimate_preserves_rest_of_task(tmp_path):
    task = tmp_path / 'task.md'
    task.write_text(TASK_TEXT)
    append_token_estimate(str(task), '## Pre-flight\n\n- Spec: 100 tokens\n')
    content = task.read_text()
    assert '## Done when' in content
    assert '## Goal' in content
