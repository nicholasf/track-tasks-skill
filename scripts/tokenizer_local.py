import sys

from tokenizer import TokenizerMixin


class LocalTokenizer(TokenizerMixin):
    source = 'local'

    def count(self, text: str) -> int:
        print('[tokenizer] using local tokenizer (tiktoken cl100k_base)', file=sys.stderr)
        try:
            import tiktoken
        except ImportError as error:
            raise RuntimeError('tiktoken is not installed; run: uv add tiktoken') from error
        enc = tiktoken.get_encoding('cl100k_base')
        result = len(enc.encode(text))
        self._print_visualisation()
        return result
