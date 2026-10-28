"""Budgeted HTTPS access; byte budgets include retry payloads, never trust ETag as SHA256."""
import re
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
from pathlib import Path


class BudgetClient:
    def __init__(self, full_budget=500 * 1024**2, regional_budget=16 * 1024**2, request_limit=100):
        self.limits = {'full': full_budget, 'regional': regional_budget}
        self.used = {'full': 0, 'regional': 0}
        self.requests = 0
        self.request_limit = request_limit
        self.evidence = []

    def head(self, url):
        """Discover payload size before a full download; HEAD payload is never consumed."""
        self.requests += 1
        if self.requests > self.request_limit:
            raise RuntimeError('Request budget exhausted')
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30) as r:
            size = int(r.headers.get('Content-Length', '-1'))
            if size < 0:
                raise ValueError('Source has no discoverable Content-Length')
            item = dict(url=url, final_url=r.url, method='HEAD', bytes=0, source_bytes=size,
                        retrieved_utc=datetime.now(timezone.utc).isoformat(),
                        last_modified=r.headers.get('Last-Modified'), server_date=r.headers.get('Date'))
            self.evidence.append(item)
            return item

    def fetch(self, url, start=None, end=None, dest=None):
        kind = 'full' if start is None else 'regional'
        headers = {'User-Agent': 'RiceFlow/0.1', 'Accept-Encoding': 'identity'}
        if start is not None:
            if end is None or end < start:
                raise ValueError('Range requires bounded end')
            headers['Range'] = f'bytes={start}-{end}'
        for attempt in range(3):
            self.requests += 1
            if self.requests > self.request_limit:
                raise RuntimeError('Request budget exhausted')
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                    size = int(r.headers.get('Content-Length', '-1'))
                    if start is not None:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', r.headers.get('Content-Range', ''))
                        if r.status != 206 or not match or int(match[1]) != start:
                            raise ValueError('Server ignored or misserved Range; prohibited full download refused')
                        if (int(match[2]) != min(end, int(match[3]) - 1)
                                or size != int(match[2]) - start + 1):
                            raise ValueError('Invalid ranged payload size')
                    if size < 0 or size > self.limits[kind] - self.used[kind]:
                        raise ValueError(f'{kind} transfer budget exceeded or unknown Content-Length')
                    data = bytearray()
                    while True:
                        block = r.read(min(1024 * 1024, self.limits[kind] - self.used[kind] + 1))
                        self.used[kind] += len(block)
                        if self.used[kind] > self.limits[kind]:
                            raise ValueError('Transfer budget exhausted during read')
                        if not block:
                            break
                        data.extend(block)
                    if len(data) != size:
                        raise OSError('Truncated HTTP response')
                    self.evidence.append(dict(url=url, final_url=r.url, method='GET', bytes=len(data),
                                              retrieved_utc=datetime.now(timezone.utc).isoformat(), range=headers.get('Range'),
                                              content_range=r.headers.get('Content-Range'),
                                              last_modified=r.headers.get('Last-Modified')))
                    if dest:
                        Path(dest).write_bytes(data)
                    return bytes(data)
            except (urllib.error.URLError, OSError):
                if attempt == 2:
                    raise
                time.sleep(0.5 * 2**attempt)


def bgzf_blocks(data):
    import struct
    import zlib
    offset, pieces = 0, []
    while offset + 18 <= len(data):
        if data[offset:offset + 3] != b'\x1f\x8b\x08':
            raise ValueError('Not BGZF')
        size = struct.unpack_from('<H', data, offset + 16)[0] + 1
        if offset + size > len(data):
            break
        pieces.append(zlib.decompress(data[offset:offset + size], 31))
        offset += size
    return b''.join(pieces)


def tabix_chunks(index, contig, start, end):
    import gzip
    import io
    import struct
    f = io.BytesIO(gzip.decompress(index))
    if f.read(4) != b'TBI\x01':
        raise ValueError('Expected TBI index')
    n, fmt, seq, beg, stop, meta, skip, names_size = struct.unpack('<8i', f.read(32))
    if fmt != 2 or seq != 1 or beg != 2 or stop != 0:
        raise ValueError('Index schema is not the VCF TBI preset')
    names = f.read(names_size).rstrip(b'\0').decode().split('\0')
    if contig not in names:
        raise ValueError('Index lacks requested contig')
    # reg2bins on zero-based half-open interval.
    lo, hi = start - 1, end - 1
    bins = {0}
    for shift, base in [(26, 1), (23, 9), (20, 73), (17, 585), (14, 4681)]:
        bins.update(range(base + (lo >> shift), base + (hi >> shift) + 1))
    chunks = []
    for name in names:
        nb = struct.unpack('<i', f.read(4))[0]
        for _ in range(nb):
            bin_id, nc = struct.unpack('<Ii', f.read(8))
            for _ in range(nc):
                a, b = struct.unpack('<QQ', f.read(16))
                if name == contig and bin_id in bins and a < b:
                    chunks.append((a, b))
        ni = struct.unpack('<i', f.read(4))[0]
        f.seek(ni * 8, 1)
    return sorted(set(chunks))


def regional_vcf(client, url, contig, start, end, out):
    import gzip
    idx = client.fetch(url + '.tbi')
    Path(str(out) + '.source.tbi').write_bytes(idx)
    prefix = client.fetch(url, 0, 262143)
    header = [x for x in bgzf_blocks(prefix).decode().splitlines() if x.startswith('#')]
    if not header or not header[-1].startswith('#CHROM'):
        raise ValueError('Header exceeds bounded prefix')
    chunks = tabix_chunks(idx, contig, start, end)
    # Merge index-overlapping virtual intervals, rather than deduplicating source records.
    # Identical duplicate rows in the source must survive retrieval and fail downstream validation.
    merged = []
    for a, b in chunks:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    lines = []
    for a, b in merged:
        payload = client.fetch(url, a >> 16, (b >> 16) + 65535)
        import struct
        import zlib
        cursor, pieces = 0, []
        last_block = (b >> 16) - (a >> 16)
        while cursor <= last_block and cursor + 18 <= len(payload):
            size = struct.unpack_from('<H', payload, cursor + 16)[0] + 1
            block = zlib.decompress(payload[cursor:cursor + size], 31)
            left = (a & 65535) if cursor == 0 else 0
            right = (b & 65535) if cursor == last_block else len(block)
            pieces.append(block[left:right])
            if cursor == last_block:
                break
            cursor += size
        raw = b''.join(pieces)
        if raw and not raw.endswith(b'\n'):
            raise ValueError('Index chunk ended inside a VCF record')
        for line in raw.decode().splitlines():
            if not line or line.startswith('#'):
                continue
            cols = line.split('\t')
            if cols[0] == contig and start <= int(cols[1]) <= end:
                lines.append(line)
    Path(out).write_text('\n'.join(header + sorted(lines, key=lambda x: int(x.split('\t')[1]))) + '\n')
    return dict(index_sha256=__import__('hashlib').sha256(idx).hexdigest(), chunks=len(chunks),
                records=len(lines), header=header, index_uncompressed_bytes=len(gzip.decompress(idx)))
