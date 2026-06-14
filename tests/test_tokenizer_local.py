import ast
import pytest
from tokenizer_local import LocalTokenizer


def test_count_returns_integer(capsys):
    tokenizer = LocalTokenizer()
    result = tokenizer.count('hello world')
    assert isinstance(result, int)
    assert result > 0


def test_count_empty_string(capsys):
    tokenizer = LocalTokenizer()
    result = tokenizer.count('')
    assert isinstance(result, int)
    assert result == 0


def test_count_longer_text_is_higher(capsys):
    tokenizer = LocalTokenizer()
    short = tokenizer.count('hello')
    long = tokenizer.count('hello world this is a longer piece of text with many tokens')
    assert long > short


def test_count_logs_to_stderr(capsys):
    tokenizer = LocalTokenizer()
    tokenizer.count('test')
    captured = capsys.readouterr()
    assert '[tokenizer] using local tokenizer (tiktoken cl100k_base)' in captured.err


def test_prints_first_20_tokens_to_stdout(capsys):
    tokenizer = LocalTokenizer()
    tokenizer.count('hello world')
    captured = capsys.readouterr()
    tokens = ast.literal_eval(captured.out.strip())
    assert isinstance(tokens, list)
    assert all(isinstance(t, int) for t in tokens)
    assert len(tokens) <= 20


def test_prints_at_most_20_tokens_for_long_text(capsys):
    tokenizer = LocalTokenizer()
    tokenizer.count('word ' * 100)
    captured = capsys.readouterr()
    tokens = ast.literal_eval(captured.out.strip())
    assert len(tokens) == 20


def test_source_label_is_local():
    tokenizer = LocalTokenizer()
    assert tokenizer.source == 'local'
