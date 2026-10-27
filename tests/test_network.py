import http.server
import threading
import pytest
from riceflow.network import BudgetClient, regional_vcf


@pytest.fixture
def server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length', '1000')
            self.end_headers()
            self.wfile.write(b'x' * 1000)
        def log_message(self, *args):
            pass
    s = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield f'http://127.0.0.1:{s.server_port}'
    s.shutdown()
    s.server_close()


def test_range_ignored_fails_before_read(server):
    c = BudgetClient()
    with pytest.raises(ValueError, match='ignored'):
        c.fetch(server, 0, 20)
    assert c.used['regional'] == 0


def test_full_budget_refuses_large_payload(server):
    c = BudgetClient(full_budget=10)
    with pytest.raises(ValueError, match='budget'):
        c.fetch(server)
    assert c.used['full'] == 0


def test_indexed_retrieval_boundaries(tmp_path):
    from pathlib import Path
    data = Path('tests/fixtures/tiny.vcf.gz').read_bytes()
    idx = Path('tests/fixtures/tiny.vcf.gz.tbi').read_bytes()
    class LocalClient:
        def fetch(self, url, start=None, end=None):
            if url.endswith('.tbi'):
                return idx
            return data[start:min(end + 1, len(data))]
    p = tmp_path / 'region.vcf'
    regional_vcf(LocalClient(), 'https://example.test/tiny.vcf.gz', 'chr01', 2, 8, p)
    positions = [int(x.split('\t')[1]) for x in p.read_text().splitlines() if not x.startswith('#')]
    assert positions == list(range(2, 9))
