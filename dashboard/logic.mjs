export const number = value => typeof value === 'number' && Number.isFinite(value);
export const fmt = value => number(value) ? new Intl.NumberFormat('en-US', {maximumFractionDigits: 2}).format(value) : '—';
export const pct = value => number(value) ? `${(value * 100).toFixed(1)}%` : '—';
export const short = value => typeof value === 'string' ? value.slice(0, 10) : '—';
export function retained(run, track) { return run?.tracks?.[track]?.final_sites?.length ?? null; }
export function selected(run, track) { return run?.tracks?.[track]?.original_sites?.length ?? run?.tracks?.[track]?.baseline_sites?.length ?? null; }
export function samples(run, track = 'cohort') { return run?.tracks?.[track]?.final_samples?.length ?? null; }
export function statusTone(status) { return ['SUCCESS', 'PASS', 'COMPLETED', 'CACHED'].includes(status) ? 'good' : ['FAILED', 'ERROR'].includes(status) ? 'bad' : 'warn'; }
export function date(value, options = {}) { const d = new Date(value); return value && Number.isFinite(d.valueOf()) ? new Intl.DateTimeFormat('en-US', {month: 'short', day: 'numeric', ...options}).format(d) : 'Not recorded'; }
export function mean(rows, field) { const values = (rows || []).map(r => r[field]).filter(number); return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null; }
export function csv(rows, keys) {
  const cell = value => { let s = value == null ? '' : String(value); if (/^[\s\uFEFF]*[=+@\-]/.test(s)) s = "'" + s; return '"' + s.replaceAll('"', '""') + '"'; };
  return [keys.map(cell).join(','), ...rows.map(row => keys.map(key => cell(row[key])).join(','))].join('\r\n');
}
export function validateBundle(data) {
  if (!data || data.schema_version !== 1 || !Array.isArray(data.runs) || data.runs.length === 0 || data.runs.length > 200) throw new Error('Choose a RiceFlow dashboard export with schema_version 1.');
  const ids = new Set();
  for (const run of data.runs) {
    if (!run || typeof run.id !== 'string' || ids.has(run.id) || typeof run.name !== 'string' || !run.tracks || typeof run.tracks !== 'object' || !run.tracks.cohort || !run.tracks.vcf || !run.policy || typeof run.policy !== 'object' || !['real','synthetic'].includes(run.kind)) throw new Error('The run list is invalid or contains duplicate identifiers.');
    for (const key of ['files','tasks','variants']) if (key in run && !Array.isArray(run[key])) throw new Error('Run artifact lists must be arrays.');
    for (const file of run.files || []) safeSourceUrl(file?.url);
    ids.add(run.id);
    for (const t of Object.values(run.tracks)) {
      if (!t || typeof t !== 'object' || Array.isArray(t)) throw new Error('Each track must be a metric object.');
      for (const key of ['baseline_samples', 'final_samples', 'baseline_sites', 'original_sites', 'final_sites']) {
        if (!(key in t)) continue;
        if (!Array.isArray(t[key]) || t[key].length > 100000) throw new Error('Run metrics exceed the supported dashboard format.');
        for (const row of t[key]) {
          if (!row || typeof row !== 'object' || typeof row[key.endsWith('samples')?'sample':'locus'] !== 'string') throw new Error('Sample and site metric identifiers must be strings.');
          if (row.call_rate != null && (!number(row.call_rate) || row.call_rate < 0 || row.call_rate > 1)) throw new Error('Call rates must be null or a finite value between zero and one.');
        }
      }
    }
    // Imported files are display inputs; a claimed marker cannot certify their biological results.
  }
  return data;
}
export function sourceLink(path, commit) { return `https://github.com/madhavanbalaji02/RiceFlow/blob/${encodeURIComponent(commit)}/${path.split('/').map(encodeURIComponent).join('/')}`; }

export function safeSourceUrl(value) { const url = new URL(value); if (url.protocol !== 'https:' || url.hostname !== 'github.com' || url.username || url.password || !url.pathname.startsWith('/madhavanbalaji02/RiceFlow/')) throw new Error('Artifact links must stay in the RiceFlow GitHub repository.'); return url.href; }
