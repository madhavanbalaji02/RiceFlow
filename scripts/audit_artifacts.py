"""Read-only revalidation of run markers, recorded hashes, data tables and embedded HTML."""
import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from riceflow.common import dump, sha
from riceflow.validation import validate_track, verify_real_inputs


class HTMLCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.titles, self.external = 0, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h1':
            self.titles += 1
        if tag == 'script' and attrs.get('src'):
            self.external.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.external.append(attrs.get('href'))


def verify(path):
    path = Path(path)
    m = json.loads((path / 'run-manifest.json').read_text())
    marker = json.loads((path / 'SUCCESS.json').read_text())
    assert marker['manifest_sha256'] == sha(path / 'run-manifest.json')
    assert marker['checksums_sha256'] == sha(path / 'output-checksums.json')
    checks = json.loads((path / 'output-checksums.json').read_text())
    assert all(sha(path / p) == h for p, h in checks.items())
    for kind in ['cohort', 'vcf']:
        validate_track(path / kind, kind)
    if m['label'].startswith('REAL'):
        cfg = dict(m['config'])
        if not Path(cfg['source_manifest']).is_file():
            # The copied manifest was checksum-verified above; controller paths may be remote.
            cfg['source_manifest'] = str(path / 'source-manifest.json')
        verify_real_inputs(cfg)
    expected = hashlib.sha256(json.dumps(m['code'], sort_keys=True).encode()).hexdigest()
    assert m['config']['execution_code_fingerprint'] == expected
    parser = HTMLCheck()
    html = (path / 'report.html').read_text()
    parser.feed(html)
    assert parser.titles == 1 and not parser.external and 'Plotly.newPlot' in html
    assert 'not improved biological accuracy' in html
    return dict(status=m['status'], track_statuses=m['track_statuses'], validated_files=len(checks),
                code_fingerprint_verified=True, embedded_charts=True, external_assets=parser.external)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', action='append', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    dump(a.out, {path: verify(path) for path in a.run})
    print(a.out)
