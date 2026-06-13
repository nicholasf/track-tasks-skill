import os
import random
from typing import Protocol, runtime_checkable

_VISUALISATION_CHARS = '▓░▒█▌▐▏▎▍▊▋▉'


@runtime_checkable
class Tokenizer(Protocol):
    source: str

    def count(self, text: str) -> int: ...


class TokenizerMixin:
    def _print_visualisation(self) -> None:
        if os.environ.get('TOKENIZER_VISUALISE', '1') != '1':
            return
        n = random.randint(10, 50)
        print(''.join(random.choice(_VISUALISATION_CHARS) for _ in range(n)))
