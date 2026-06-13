import os
import pytest
from tokenizer_local import LocalTokenizer


@pytest.fixture(autouse=True)
def suppress_visualisation(monkeypatch):
    monkeypatch.setenv('TOKENIZER_VISUALISE', '0')


def test_count_returns_integer():
    tokenizer = LocalTokenizer()
    result = tokenizer.count('hello world')
    assert isinstance(result, int)
    assert result > 0


def test_count_empty_string():
    tokenizer = LocalTokenizer()
    result = tokenizer.count('')
    assert isinstance(result, int)
    assert result == 0


def test_count_longer_text_is_higher():
    tokenizer = LocalTokenizer()
    short = tokenizer.count('hello')
    long = tokenizer.count('hello world this is a longer piece of text with many tokens')
    assert long > short


def test_count_logs_to_stderr(capsys):
    tokenizer = LocalTokenizer()
    tokenizer.count('test')
    captured = capsys.readouterr()
    assert '[tokenizer] using local tokenizer (tiktoken cl100k_base)' in captured.err


def test_visualisation_suppressed_by_env_var(capsys):
    tokenizer = LocalTokenizer()
    tokenizer.count('test')
    captured = capsys.readouterr()
    assert captured.out == ''


def test_source_label_is_local():
    tokenizer = LocalTokenizer()
    assert tokenizer.source == 'local'
