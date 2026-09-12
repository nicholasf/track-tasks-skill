"""Serialize a Pydantic model to TOML.

Python's stdlib `tomllib` reads TOML but deliberately does not write it, and
Pydantic has no TOML mode — only dict (`model_dump`) and JSON. This module is
the missing step between them.

It is deliberately not a general-purpose TOML writer. It handles the shapes a
Pydantic model actually produces, and it makes one opinionated choice a
general writer would not: multi-line prose is emitted as a TOML *literal*
string (`'''`), which does no escape processing, so prose round-trips verbatim
and stays readable to a human — or to a model — reading the file directly.
A writer such as `tomli-w` would escape it into a single basic string instead.

TOML has no null. A `None` value cannot be represented, so those keys are
omitted entirely rather than guessed at.
"""

from typing import Any

from pydantic import BaseModel


def dumps(model: BaseModel) -> str:
    """Serialize a Pydantic model to a TOML document."""
    return dumps_dict(model.model_dump(mode='json'))


def dumps_dict(data: dict[str, Any]) -> str:
    """Serialize a plain dict to a TOML document.

    Key order within each group is preserved; the groups themselves are not
    interleaved — see `_partition`. Tables nest: a dict value becomes a
    `[table]`, and a dict inside that becomes a dotted `[table.sub]` header,
    so a dict of dicts round-trips through `tomllib`.
    """
    scalars, tables, table_arrays = _partition(data)

    lines = [f'{key} = {format_value(value)}' for key, value in scalars.items()]

    for name, table in tables.items():
        lines += _emit_table(name, table)

    for name, rows in table_arrays.items():
        for row in rows:
            lines += ['', f'[[{name}]]']
            lines += [f'{k} = {format_value(v)}' for k, v in row.items() if v is not None]

    return '\n'.join(lines) + '\n'


def _emit_table(name: str, table: dict[str, Any]) -> list[str]:
    """Emit a `[name]` header and its contents, recursing into sub-tables.

    The table's own scalar keys are emitted before any sub-table header, so
    the ordering rule `_partition` enforces at the top level holds at every
    level of nesting.
    """
    scalars, tables, table_arrays = _partition(table)

    lines = ['', f'[{name}]']
    lines += [f'{k} = {format_value(v)}' for k, v in scalars.items()]

    for sub_name, sub_table in tables.items():
        lines += _emit_table(f'{name}.{sub_name}', sub_table)

    for sub_name, rows in table_arrays.items():
        for row in rows:
            lines += ['', f'[[{name}.{sub_name}]]']
            lines += [f'{k} = {format_value(v)}' for k, v in row.items() if v is not None]

    return lines


def _partition(
    data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict], dict[str, list[dict]]]:
    """Split a dict into scalars, sub-tables, and arrays of tables.

    TOML binds every bare key to the most recently opened table header, so all
    top-level scalars have to be written before any `[table]` or `[[array]]`
    header appears. Partitioning first is what guarantees that ordering,
    regardless of the order the fields are declared on the model.
    """
    scalars: dict[str, Any] = {}
    tables: dict[str, dict] = {}
    table_arrays: dict[str, list[dict]] = {}

    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            if value:
                tables[key] = value
        elif _is_table_array(value):
            table_arrays[key] = value
        else:
            scalars[key] = value

    return scalars, tables, table_arrays


def _is_table_array(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(isinstance(v, dict) for v in value)


def format_value(value: Any) -> str:
    """Render a single Python value as a TOML value."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(format_value(v) for v in value) + ']'
    return _format_string(str(value))


def _format_string(text: str) -> str:
    if '\n' in text and _literal_safe(text):
        # Literal multi-line string — no escape processing, so prose round-trips
        # verbatim. TOML discards the newline immediately after the opening
        # delimiter, which is why the content can start on the next line.
        return f"'''\n{text}'''"
    return '"' + _escape(text) + '"'


def _literal_safe(text: str) -> bool:
    """Whether text can be held in a `'''` literal string without corruption.

    A literal string cannot contain its own delimiter, and cannot end with a
    quote — that would run into the closing delimiter and change where the
    string ends.
    """
    return "'''" not in text and not text.endswith("'")


def _escape(text: str) -> str:
    out = text.replace('\\', '\\\\').replace('"', '\\"')
    return out.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
