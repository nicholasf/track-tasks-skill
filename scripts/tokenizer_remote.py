import json
import urllib.request

from tokenizer import TokenizerMixin


class RemoteTokenizer(TokenizerMixin):
    source = 'remote'

    def __init__(
        self,
        hostname: str,
        backend: str = 'llama-server',
        model: str = '',
        port: int | None = None,
    ) -> None:
        self._hostname = hostname
        self._backend = backend
        self._model = model
        self._port = port or (9337 if backend == 'llama-server' else 11434)

    def probe(self) -> None:
        """Verify the endpoint is reachable. Raises RuntimeError on failure."""
        url = f'http://{self._hostname}:{self._port}/health'
        try:
            urllib.request.urlopen(url, timeout=5)
        except Exception as error:
            raise RuntimeError(f'remote tokenizer unreachable at {url}: {error}') from error

    def count(self, text: str) -> int:
        if self._backend == 'llama-server':
            result = self._tokenize_llama(text)
        else:
            result = self._tokenize_ollama(text)
        self._print_visualisation()
        return result

    def _tokenize_llama(self, text: str) -> int:
        body = json.dumps({'content': text}).encode()
        req = urllib.request.Request(
            f'http://{self._hostname}:{self._port}/tokenize',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
        return len(data.get('tokens', []))

    def _tokenize_ollama(self, text: str) -> int:
        body = json.dumps({'model': self._model, 'prompt': text}).encode()
        req = urllib.request.Request(
            f'http://{self._hostname}:{self._port}/api/tokenize',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
        return len(data.get('tokens', []))
