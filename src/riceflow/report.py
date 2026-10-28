import json
from pathlib import Path

import plotly.graph_objects as go
from jinja2 import Environment, select_autoescape

from .common import dump, sha


def build(out, label, execution=None):
    out = Path(out)
    tracks = {}
    for track in ['cohort', 'vcf']:
        p = out / track / 'summary.json'
        tracks[track] = json.loads(p.read_text()) if p.exists() else {'status': 'BLOCKED'}
    source_file = out / 'source-manifest.json'
    source = json.loads(source_file.read_text()) if source_file.exists() else {'status': 'SYNTHETIC', 'context': 'Hand-constructed fixtures; not real-data scientific validation'}
    charts = []
    for name, result in tracks.items():
        if 'baseline_samples' not in result:
            continue
        fig = go.Figure()
        for stage in ['baseline', 'final']:
            rows = result[stage + '_samples']
            fig.add_bar(name=stage, x=[r['sample'] for r in rows], y=[r['call_rate'] for r in rows],
                        customdata=[[r['complete'], r['sites']] for r in rows],
                        hovertemplate='%{x}: %{customdata[0]}/%{customdata[1]} observed SNP sites = %{y}<extra>%{fullData.name}</extra>')
        fig.update_layout(title=f'{name}: call rate with stage-specific site denominators (selection, not accuracy)', yaxis_range=[0, 1], barmode='group')
        charts.append(fig.to_html(full_html=False, include_plotlyjs=True if not charts else False))
    template = Environment(autoescape=select_autoescape(default=True)).from_string('''<!doctype html>
<html lang="en"><meta charset="utf-8"><title>RiceFlow QC report</title>
<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px}pre{white-space:pre-wrap;
background:#f4f6f8;padding:20px}h1,h2{color:#164e36}</style>
<h1>RiceFlow — {{ label }}</h1><h2>Execution and provenance</h2><pre>{{ execution|tojson(indent=2) }}</pre><p>Downstream QC and workflow engineering. Tracks are separate;
these data do not constitute a jointly called cohort. Success requires the launcher's SUCCESS.json.</p>
<p>Complete diploid genotypes alone contribute alleles. Partial calls count as uncalled. Call rate denominator:
observed selected SNP sites per sample, retained samples per site. Empty denominators are null.
Cohort allele1 frequency describes BIM A1, not verified ALT. Heterozygosity is descriptive;
no HWE filter or default frequency filter is applied. Baseline and final bars may use different site sets; hover for their exact denominators. Increased completeness among retained records reflects masking and exclusion, not improved biological accuracy.</p>
{% for chart in charts %}{{ chart|safe }}{% endfor %}
{% for name,result in tracks.items() %}<h2>{{ name }}: {{ result.status }}</h2>
<pre>{{ result|tojson(indent=2) }}</pre>{% endfor %}
<h2>Source validation</h2><pre>{{ source|tojson(indent=2) }}</pre><h2>Limitations</h2><p>Thresholds are configurable choices, not validated biological cutoffs.
Single-accession regional VCF observations are not whole-genome measurements. Reference calls and unsupported
variants are counted outside the SNP metric denominator. Not-assessed qualities are masked conservatively and
reported separately from failures. Source FILTER flags are preserved, not reinterpreted.
Already pruned CoreSNP data cannot reproduce raw discovery, LD structure, or original DP/GQ filtering.
No imputation, pangenome analysis, or population discovery is claimed.</p></html>''')
    (out / 'report.html').write_text(template.render(label=label, tracks=tracks, charts=charts, source=source, execution=execution or {'status': 'Report regenerated; inspect run-manifest.json and SUCCESS.json'}))
    dump(out / 'output-checksums.json', {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                                       if p.is_file() and p.name not in ['output-checksums.json', 'SUCCESS.json',
                                                                         'run-manifest.json']})
    return tracks
