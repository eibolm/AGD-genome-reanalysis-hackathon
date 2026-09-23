"""Local web GUI for hpo-scribe.

    python server.py            # then open http://127.0.0.1:8765

Standard library HTTP server so the only dependency in the project is `anthropic`.
Binds to loopback only; this is a single-user annotation tool, not a service.

Endpoints:
    GET  /                 the page
    GET  /api/vocab        vocabulary size and release
    GET  /api/search?q=    lexical search over the allowed vocabulary (no API call)
    POST /api/annotate     {text, annotator} -> the full annotation
    POST /api/save         append a confirmed annotation to annotations.jsonl
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
import webbrowser
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import hpo_vocab

HERE = Path(__file__).parent
PAGE = HERE / 'web' / 'index.html'
OUT = HERE / 'annotations.jsonl'
HOST, PORT = '127.0.0.1', 8765

VOCAB = None          # loaded at startup
VOCAB_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = 'hpo-scribe'

    def log_message(self, fmt, *args):
        sys.stderr.write(f'  {self.address_string()} {fmt % args}\n')

    # -- helpers -------------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode('utf-8'), 'application/json')

    def _body(self) -> dict:
        length = int(self.headers.get('Content-Length') or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode('utf-8'))

    # -- routes --------------------------------------------------------------
    def do_GET(self):
        route = urlparse(self.path)
        if route.path in ('/', '/index.html'):
            if not PAGE.exists():
                return self._send(500, b'web/index.html is missing', 'text/plain')
            return self._send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')

        if route.path == '/api/vocab':
            return self._json(200, {
                'size': len(VOCAB.terms),
                'release': VOCAB.release,
                'model': os.environ.get('HPO_SCRIBE_MODEL', 'claude-opus-5'),
                'have_key': bool(os.environ.get('ANTHROPIC_API_KEY')
                                 or os.environ.get('ANTHROPIC_AUTH_TOKEN')),
                'saved': sum(1 for _ in OUT.open(encoding='utf-8')) if OUT.exists() else 0,
            })

        if route.path == '/api/search':
            q = (parse_qs(route.query).get('q') or [''])[0]
            hits = VOCAB.search(q, limit=12)
            return self._json(200, {'results': [asdict(h) for h in hits]})

        return self._send(404, b'not found', 'text/plain')

    def do_POST(self):
        route = urlparse(self.path)
        try:
            body = self._body()
        except ValueError:
            return self._json(400, {'error': 'malformed JSON body'})

        if route.path == '/api/annotate':
            text = (body.get('text') or '').strip()
            if not text:
                return self._json(400, {'error': 'no text supplied'})
            # Imported lazily so the page still loads and manual search still works
            # when the SDK or the API key is not set up yet.
            try:
                import annotate as pipeline
            except ImportError as exc:
                return self._json(500, {'error': f'cannot import pipeline: {exc}'})
            try:
                with VOCAB_LOCK:
                    result = pipeline.annotate(
                        text, VOCAB, annotator=body.get('annotator') or 'unknown')
                return self._json(200, result.to_dict())
            except Exception as exc:                        # noqa: BLE001
                traceback.print_exc()
                return self._json(502, {'error': f'{type(exc).__name__}: {exc}'})

        if route.path == '/api/save':
            record = body.get('record')
            if not isinstance(record, dict):
                return self._json(400, {'error': 'no record supplied'})
            record['saved_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            bad = [t for t in record.get('terms', [])
                   if not VOCAB.is_allowed(t.get('hpo_id', ''))]
            if bad:
                # The export is the training data. Nothing outside the vocabulary
                # reaches it, even if the page sends it.
                return self._json(400, {
                    'error': f'refused: {len(bad)} term(s) not in phenotype.hpoa',
                    'terms': [t.get('hpo_id') for t in bad],
                })
            with OUT.open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + '\n')
            return self._json(200, {
                'ok': True,
                'file': str(OUT),
                'saved': sum(1 for _ in OUT.open(encoding='utf-8')),
            })

        return self._send(404, b'not found', 'text/plain')


def main() -> None:
    global VOCAB
    print('loading vocabulary...')
    VOCAB = hpo_vocab.load()
    print(f'  {len(VOCAB.terms)} allowed terms from phenotype.hpoa '
          f'({VOCAB.release})')

    if not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')):
        print('\n  ANTHROPIC_API_KEY is not set - the page will load and manual term')
        print('  search will work, but annotation will fail until you set it.\n')

    url = f'http://{HOST}:{PORT}'
    print(f'serving {url}  (ctrl-c to stop)')
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped')
        server.server_close()


if __name__ == '__main__':
    main()
