import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import cohort, vcf
from .common import Policy, RunConfig, command, dump, sha
from .report import build

ROOT = Path(__file__).resolve().parents[2]


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def finalize(out, manifest, code, error=None):
    manifest.update(ended=timestamp(), returncode=code, error=error)
    trace = out / 'trace.tsv'
    if trace.exists():
        import csv
        with trace.open() as f:
            manifest['tasks'] = list(csv.DictReader(f, delimiter='\t'))
    manifest['task_tools'] = {track: (out / track / 'tool-versions.txt').read_text()
                              for track in ['cohort', 'vcf'] if (out / track / 'tool-versions.txt').exists()}
    ok = False
    try:
        execution = {k: manifest.get(k) for k in ['run_id', 'fingerprint', 'label', 'started', 'ended',
                    'elapsed_seconds', 'returncode', 'tools', 'task_tools', 'git', 'image', 'tasks', 'config']}
        execution['resource_limitations'] = 'Native macOS lacks per-task CPU/RSS telemetry; elapsed is measured wall time.'
        tracks = build(out, manifest['label'], execution)
        ok = code == 0 and all(t.get('status') == 'PASS' for t in tracks.values())
        if ok:
            checks = json.loads((out / 'output-checksums.json').read_text())
            for name, digest in checks.items():
                if sha(out / name) != digest:
                    raise ValueError('Output checksum mismatch')
            import pyarrow.parquet as pq
            for track in ['cohort', 'vcf']:
                if pq.read_table(out / track / 'final_samples.parquet').num_rows == 0:
                    raise ValueError('Required sample table is empty')
            cohort.validate(out / 'cohort' / 'filtered')
            import pysam
            with pysam.VariantFile(str(out / 'vcf' / 'filtered.vcf.gz')) as f:
                if not list(f.fetch()):
                    raise ValueError('Required VCF records are empty')
            for name in ['execution.html', 'timeline.html', 'trace.tsv']:
                if not (out / name).is_file():
                    raise ValueError(f'Required Nextflow diagnostic absent: {name}')
    except Exception as e:
        ok = False
        manifest['error'] = str(e)
    manifest['status'] = 'SUCCESS' if ok else 'FAILED' if code or manifest.get('error') else 'INCOMPLETE'
    dump(out / 'run-manifest.json', manifest)
    if ok:
        dump(out / 'SUCCESS.json', {'run_id': manifest['run_id'],
                                  'manifest_sha256': sha(out / 'run-manifest.json'),
                                  'checksums_sha256': sha(out / 'output-checksums.json')})
    else:
        dump(out / 'failure-manifest.json', manifest)
    return 0 if ok else 1


def launch(args):
    cfg_path = Path(args.config).resolve()
    cfg = RunConfig(**yaml.safe_load(cfg_path.read_text())).checked().model_dump()
    policy = Policy(**cfg['policy'])
    if args.profile == 'aws':
        from .cloud import authorize
        authorize(os.environ['RICEFLOW_CLOUD_AUTHORIZATION'])
        args.image = os.environ['RICEFLOW_IMAGE']
        if '@sha256:' not in args.image:
            raise ValueError('AWS requires an immutable ECR RepoDigest')
    if args.profile == 'docker':
        args.image = command(['docker', 'image', 'inspect', args.image or 'riceflow:0.1.0',
                              '--format', '{{.Id}}']).strip()
    if cfg['track_label'].startswith('REAL'):
        source = json.loads(Path(cfg['source_manifest']).read_text())
        if source['tracks']['cohort']['status'] != 'VERIFIED':
            raise ValueError('Real cohort has not passed preflight')
        for entry in source['sources']:
            if 'decompressed_sha256' in entry:
                ext = entry['url'].split('.')[-2]
                actual = ((cfg.get('input_sha256') or {}).get('cohort.' + ext)
                          if cfg['cohort'].startswith('s3://') else sha(cfg['cohort'] + '.' + ext))
                if actual != entry['decompressed_sha256']:
                    raise ValueError('Cohort checksum no longer matches preflight')
        if cfg.get('vcf') and (source.get('reference', {}).get('status') != 'VERIFIED_REGIONAL_BASES'
                               or source['reference']['sha256'] != ((cfg.get('input_sha256') or {}).get('reference')
                                   if cfg['reference'].startswith('s3://') else sha(cfg['reference']))):
            raise ValueError('Real VCF requires the verified matching reference from preflight')
    # Paths are resolved at the launcher, then staged by Nextflow for local/container/cloud use.
    for key in ['cohort', 'vcf', 'reference']:
        if cfg.get(key) and not cfg[key].startswith('s3://'):
            cfg[key] = str(Path(cfg[key]).resolve())
    inputs = {key: sha(p) for key in ['vcf', 'reference'] if (p := cfg.get(key)) and Path(p).exists()}
    for ext in ['bed', 'bim', 'fam']:
        p = cfg['cohort'] + '.' + ext
        inputs['cohort.' + ext] = ((cfg.get('input_sha256') or {})['cohort.' + ext]
                                  if p.startswith('s3://') else sha(p))
    if any((cfg.get(k) or '').startswith('s3://') for k in ['cohort', 'vcf', 'reference']):
        if args.profile != 'aws' or not cfg.get('input_sha256'):
            raise ValueError('S3 inputs require authorized AWS mode and verified input_sha256 metadata')
        for key in ['vcf', 'reference']:
            if cfg.get(key):
                inputs[key] = cfg['input_sha256'][key]
    cfg['policy'] = policy.model_dump()
    cfg['input_sha256'] = inputs
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for folder in ['src', 'modules', 'workflows', 'conf']
                     for p in sorted((ROOT / folder).rglob('*')) if p.is_file() and '__pycache__' not in str(p)}
    source_hashes['nextflow.config'] = sha(ROOT / 'nextflow.config')
    environment = dict(profile=args.profile, image=args.image or 'native',
                       toolchain=sha(ROOT / 'config/toolchain.yaml'), requirements=sha(ROOT / 'requirements.lock'))
    fingerprint = hashlib.sha256(json.dumps(dict(config=cfg, inputs=inputs, code=source_hashes,
                                                environment=environment),
                                            sort_keys=True).encode()).hexdigest()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    out = Path(args.out or ROOT / 'reports' / run_id).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Run output directory must be new/empty; resume uses a new run path')
    out.mkdir(parents=True, exist_ok=True)
    dump(out / 'resolved-config.json', cfg)
    dump(out / 'policy.json', policy.model_dump())
    versions = {'python': sys.version, 'platform': platform.platform()}
    from importlib.metadata import version
    versions.update({p: version(p) for p in ['pydantic', 'PyYAML', 'pysam', 'pyarrow', 'Jinja2', 'plotly']})
    for tool, flags in [('nextflow', ['-version']), ('plink2', ['--version']),
                        ('bcftools', ['--version']), ('samtools', ['--version']), ('java', ['-version'])]:
        try:
            p = subprocess.run([tool, *flags], text=True, capture_output=True, timeout=30)
            versions[tool] = (p.stdout + p.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            versions[tool] = 'UNAVAILABLE: ' + str(e)
    try:
        git = dict(commit=command(['git', '-C', ROOT, 'rev-parse', 'HEAD']).strip(),
                   dirty=bool(command(['git', '-C', ROOT, 'status', '--porcelain']).strip()))
    except RuntimeError:
        git = dict(commit=None, dirty=None, status='not a Git repository')
    manifest = dict(run_id=run_id, fingerprint=fingerprint, started=timestamp(), status='RUNNING',
                    label=cfg['track_label'], git=git, tools=versions, inputs=inputs,
                    code=source_hashes, config=cfg, image=args.image or 'NATIVE_NO_IMAGE',
                    source_manifest=cfg.get('source_manifest'), attempts=[],
                    metric_definitions='docs/DATA_DICTIONARY.md')
    if cfg.get('source_manifest'):
        shutil.copy(cfg['source_manifest'], out / 'source-manifest.json')
    dump(out / 'run-manifest.json', manifest)
    nf = ['nextflow', '-log', str(out / 'nextflow.log'), 'run', str(ROOT / 'workflows/main.nf'),
          '-c', str(ROOT / 'nextflow.config'), '-profile', 'native' if args.profile == 'aws' else args.profile,
          '--config_json', str(out / 'resolved-config.json'), '--policy', str(out / 'policy.json'),
          '--outdir', str(out), '--inject_failure', str(args.inject_failure).lower(),
          '-with-report', str(out / 'execution.html'), '-with-timeline', str(out / 'timeline.html'),
          '-with-trace', str(out / 'trace.tsv')]
    if args.profile == 'aws':
        nf += ['-c', str(ROOT / 'conf/aws.config')]
    if args.image:
        nf += ['--image', args.image]
    if args.resume:
        nf += ['-resume', args.resume]
    start = time.monotonic()
    child = None
    try:
        with (out / 'launcher.log').open('w') as log:
            child = subprocess.Popen(nf, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = child.wait(timeout=args.deadline)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                code = 124
        manifest['elapsed_seconds'] = time.monotonic() - start
        return finalize(out, manifest, code)
    except (Exception, KeyboardInterrupt) as e:
        if child and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=30)
        manifest['elapsed_seconds'] = time.monotonic() - start
        return finalize(out, manifest, 1, str(e))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('run')
    q.add_argument('--config', default='config/demo.yaml')
    q.add_argument('--out')
    q.add_argument('--profile', choices=['native', 'docker', 'aws'], default='native')
    q.add_argument('--image')
    q.add_argument('--resume', help='Exact previous Nextflow session name or UUID')
    q.add_argument('--inject-failure', action='store_true')
    q.add_argument('--deadline', type=int, default=1800)
    for name in ['cohort', 'vcf']:
        q = sub.add_parser(name)
        q.add_argument('--config', required=True)
        q.add_argument('--policy', required=True)
        q.add_argument('--out', required=True)
    q = sub.add_parser('report')
    q.add_argument('--out', required=True)
    q.add_argument('--label', default='UNSPECIFIED')
    a = p.parse_args()
    if a.cmd == 'run':
        return launch(a)
    if a.cmd == 'report':
        if (Path(a.out) / 'SUCCESS.json').exists():
            raise ValueError('Successful run artifacts are immutable; regenerate into an uncertified copy')
        build(a.out, a.label)
        return 0
    cfg = json.loads(Path(a.config).read_text())
    policy = Policy(**json.loads(Path(a.policy).read_text()))
    expected = cfg.get('input_sha256') or {}
    for key in (['cohort.bed', 'cohort.bim', 'cohort.fam'] if a.cmd == 'cohort' else ['vcf', 'reference']):
        path = cfg['cohort'] + '.' + key.split('.')[1] if key.startswith('cohort.') else cfg[key]
        if expected.get(key) and sha(path) != expected[key]:
            raise ValueError(f'Staged input checksum mismatch: {key}')
    if a.cmd == 'cohort':
        cohort.run(cfg['cohort'], a.out, policy, cfg['chrom'], cfg['start'], cfg['end'], cfg['sample_count'])
    else:
        vcf.run(cfg['vcf'], cfg['reference'], a.out, policy, cfg.get('expected_sample'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
