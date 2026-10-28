#!/usr/bin/env python3
"""Build only the public, read-only dashboard. Does not call AWS or run genomics."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from export_dashboard import build

ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_KEYS = {'aws_access_key_id', 'aws_secret_access_key', 'aws_session_token',
                  'credentials', 'access_token', 'account_id', 'budget_email', 'nextflow_command'}
PRIVATE_TEXT = re.compile(r'/(?:Users|home|opt|private|var/folders)/|[A-Z]:\\(?:Users|Windows)\\|'
                          r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|arn:aws[^:]*:|(?<![\w-])\d{12}(?![\w-])|'
                          r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def check_snapshot(value, location='$'):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in SENSITIVE_KEYS:
                raise ValueError(f'Private metadata field at {location}.{key}')
            check_snapshot(child, f'{location}.{key}')
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_snapshot(child, f'{location}[{index}]')
    elif isinstance(value, str) and PRIVATE_TEXT.search(value):
        raise ValueError(f'Private metadata detected at {location}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def publish(repo, output):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    if output == repo or output in repo.parents or output.is_relative_to(repo / 'dashboard'):
        raise ValueError('Choose a dedicated build directory outside dashboard source')
    manifest_path = output.parent / (output.name + '-manifest.json')
    if output.exists():
        if output.is_symlink() or not manifest_path.is_file():
            raise ValueError('Existing output is not a publisher-owned build')
        old = json.loads(manifest_path.read_text())
        actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
        if actual != set(old['assets']) or any(p.is_symlink() for p in output.rglob('*')):
            raise ValueError('Existing build contains unexpected files; preserve it and choose a new output')
        if any(digest((output / name).read_bytes()) != asset['sha256'] for name, asset in old['assets'].items()):
            raise ValueError('Existing build was edited; preserve it and choose a new output')
    snapshot = build(repo)
    if not snapshot['runs'] or any(r['certification']['state'] == 'mismatch' for r in snapshot['runs']):
        raise ValueError('Recorded run certification failed; public export refused')
    check_snapshot(snapshot)
    source = repo / 'dashboard'
    encoded = json.dumps(snapshot, separators=(',', ':'), allow_nan=False).encode()
    assets = {}

    def asset(stem, extension, body, content_type):
        name = f'assets/{stem}.{digest(body)[:16]}.{extension}'
        assets[name] = {'body': body, 'content_type': content_type,
                        'cache_control': 'public,max-age=31536000,immutable'}
        return name

    data_name = asset('data', 'json', encoded, 'application/json; charset=utf-8')
    logic_name = asset('logic', 'mjs', (source / 'logic.mjs').read_bytes(), 'text/javascript; charset=utf-8')
    app = (source / 'app.js').read_text()
    assert "from './logic.mjs'" in app and "fetch('./data.json'" in app
    app = app.replace("from './logic.mjs'", f"from './{Path(logic_name).name}'")
    app = app.replace("fetch('./data.json'", f"fetch(new URL('./{Path(data_name).name}', import.meta.url)")
    app_name = asset('app', 'js', app.encode(), 'text/javascript; charset=utf-8')
    css_name = asset('styles', 'css', (source / 'styles.css').read_bytes(), 'text/css; charset=utf-8')
    icon_name = asset('icon', 'svg', (source / 'icon.svg').read_bytes(), 'image/svg+xml')
    html = (source / 'index.html').read_text()
    for old, new in [('app.js', app_name), ('styles.css', css_name), ('icon.svg', icon_name)]:
        html = html.replace(f'"{old}"', f'"./{new}"')
    assets['index.html'] = {'body': html.encode(), 'content_type': 'text/html; charset=utf-8',
                            'cache_control': 'public,max-age=0,must-revalidate'}
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.dashboard-', dir=output.parent))
    try:
        for name, value in assets.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value['body'])
        if output.exists():
            shutil.rmtree(output)
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    manifest = {'schema_version': 1, 'source_commit': snapshot['source_commit'],
                'assets': {name: {**{k: v for k, v in value.items() if k != 'body'},
                                  'sha256': digest(value['body']), 'bytes': len(value['body'])}
                           for name, value in assets.items()},
                'total_bytes': sum(len(a['body']) for a in assets.values()),
                'run_statuses': [r['status'] for r in snapshot['runs']]}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/dashboard')
    args = parser.parse_args()
    result = publish(args.repo, args.output)
    print(json.dumps({'files': len(result['assets']), 'bytes': result['total_bytes'],
                      'output': str(args.output), 'statuses': result['run_statuses']}))


if __name__ == '__main__':
    main()
