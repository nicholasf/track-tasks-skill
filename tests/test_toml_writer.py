import tomllib

from pydantic import BaseModel

from toml_writer import dumps, dumps_dict, format_value


# ── scalars ───────────────────────────────────────────────────────────────────

def test_bool_is_lowercase():
    assert format_value(True) == 'true'
    assert format_value(False) == 'false'


def test_numbers_are_bare():
    assert format_value(3) == '3'
    assert format_value(1.5) == '1.5'


def test_bool_is_not_treated_as_int():
    # bool subclasses int in Python — the check has to come first.
    assert format_value(True) != '1'


def test_single_line_string_is_quoted():
    assert format_value('hello') == '"hello"'


def test_quotes_and_backslashes_are_escaped():
    assert format_value('say "hi"') == '"say \\"hi\\""'
    assert format_value('a\\b') == '"a\\\\b"'


def test_list_of_scalars_is_inline():
    assert format_value(['a', 'b']) == '["a", "b"]'


def test_empty_list_is_inline():
    assert format_value([]) == '[]'


# ── multi-line prose ──────────────────────────────────────────────────────────

def test_multiline_uses_literal_string():
    assert format_value('one\ntwo') == "'''\none\ntwo'''"


def test_literal_string_does_not_escape_prose():
    prose = 'Use grep with \\. and "quotes"\nacross two lines'
    assert '\\\\' not in format_value(prose)


def test_multiline_prose_round_trips_verbatim():
    prose = 'Path: C:\\temp\nRegex: \\d+ and "quoted"\nDone.'
    parsed = tomllib.loads(dumps_dict({'body': prose}))
    assert parsed['body'] == prose


def test_multiline_containing_literal_delimiter_falls_back():
    text = "before ''' after\nsecond line"
    parsed = tomllib.loads(dumps_dict({'body': text}))
    assert parsed['body'] == text


def test_multiline_ending_in_quote_falls_back():
    text = "it ends with a quote\n'"
    parsed = tomllib.loads(dumps_dict({'body': text}))
    assert parsed['body'] == text


# ── structure ─────────────────────────────────────────────────────────────────

def test_scalars_precede_tables():
    # TOML binds bare keys to the last opened header, so a scalar written after
    # a [table] header would silently land inside that table.
    out = dumps_dict({'results': {'tests': 'pass'}, 'title': 'after'})
    parsed = tomllib.loads(out)
    assert parsed['title'] == 'after'
    assert parsed['results'] == {'tests': 'pass'}


def test_nested_dict_becomes_table():
    parsed = tomllib.loads(dumps_dict({'results': {'tests': 'pass', 'summary': 'ok'}}))
    assert parsed['results'] == {'tests': 'pass', 'summary': 'ok'}


def test_list_of_dicts_becomes_array_of_tables():
    data = {'attempts': [{'agent': 'a', 'reason': 'one'}, {'agent': 'b', 'reason': 'two'}]}
    parsed = tomllib.loads(dumps_dict(data))
    assert len(parsed['attempts']) == 2
    assert parsed['attempts'][0]['agent'] == 'a'
    assert parsed['attempts'][1]['reason'] == 'two'


def test_array_of_tables_keeps_scalars_at_top():
    data = {'attempts': [{'agent': 'a'}], 'title': 'still top level'}
    parsed = tomllib.loads(dumps_dict(data))
    assert parsed['title'] == 'still top level'


def test_empty_dict_is_omitted():
    assert 'results' not in tomllib.loads(dumps_dict({'title': 't', 'results': {}}))


def test_empty_list_is_kept_as_array():
    # An empty list is an empty array, not an absent array of tables.
    assert tomllib.loads(dumps_dict({'changes': []}))['changes'] == []


def test_none_is_omitted():
    # TOML has no null, so the key cannot be written at all.
    assert 'missing' not in tomllib.loads(dumps_dict({'title': 't', 'missing': None}))


def test_none_inside_table_is_omitted():
    parsed = tomllib.loads(dumps_dict({'results': {'tests': 'pass', 'skip': None}}))
    assert parsed['results'] == {'tests': 'pass'}


# ── nested tables ─────────────────────────────────────────────────────────────

def test_two_level_nested_dict_round_trips():
    data = {'sections': {'1': {'title': 'a', 'goal': 'b'}, '2': {'title': 'c', 'goal': 'd'}}}
    out = dumps_dict(data)
    assert '[sections.1]' in out
    assert '[sections.2]' in out
    assert tomllib.loads(out) == data


def test_nested_table_whose_parent_has_scalar_keys():
    data = {'sections': {'note': 'top', '1': {'title': 'a'}}, 'title': 't'}
    parsed = tomllib.loads(dumps_dict(data))
    assert parsed == data
    assert parsed['sections']['note'] == 'top'
    assert parsed['sections']['1'] == {'title': 'a'}


def test_three_levels_of_nesting_round_trip():
    data = {'a': {'b': {'c': {'d': 'deep'}}}}
    out = dumps_dict(data)
    assert '[a.b.c]' in out
    assert tomllib.loads(out) == data


def test_empty_nested_dict_is_omitted():
    data = {'sections': {'1': {'title': 'a'}, '2': {}}}
    parsed = tomllib.loads(dumps_dict(data))
    assert parsed == {'sections': {'1': {'title': 'a'}}}


# ── pydantic entry point ──────────────────────────────────────────────────────

class _Attempt(BaseModel):
    agent: str = ''
    reason: str = ''


class _Model(BaseModel):
    title: str = ''
    count: int = 0
    tags: list[str] = []
    attempts: list[_Attempt] = []


def test_dumps_accepts_a_pydantic_model():
    parsed = tomllib.loads(dumps(_Model(title='t', count=2, tags=['x'])))
    assert parsed == {'title': 't', 'count': 2, 'tags': ['x'], 'attempts': []}


def test_dumps_renders_nested_models_as_array_of_tables():
    model = _Model(title='t', attempts=[_Attempt(agent='pond', reason='truncated')])
    parsed = tomllib.loads(dumps(model))
    assert parsed['attempts'] == [{'agent': 'pond', 'reason': 'truncated'}]


def test_dumps_output_is_valid_toml_for_realistic_prose():
    model = _Model(
        title='Refresh docs',
        attempts=[_Attempt(agent='pond-qwen', reason='Hit 32,767 tokens.\nNo edits made.')],
    )
    parsed = tomllib.loads(dumps(model))
    assert parsed['attempts'][0]['reason'] == 'Hit 32,767 tokens.\nNo edits made.'
