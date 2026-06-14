from typing import Protocol, runtime_checkable


@runtime_checkable
class Tokenizer(Protocol):
    source: str

    def count(self, text: str) -> int: ...


class TokenizerMixin:
    def _print_tokens(self, tokens: list[int]) -> None:
        print(tokens[:20])
