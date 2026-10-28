# RiceFlow dashboard

A dependency-free, read-only dashboard for recorded RiceFlow QC runs. It displays actual artifact snapshots, not live job or AWS monitoring.

## Run locally

From the repository root:

```bash
python3 scripts/export_dashboard.py
python3 -m http.server 8000 --directory dashboard
```

Open http://localhost:8000. No Node dependencies, pipeline tools, cloud credentials, or billable infrastructure are required to view it.

The exporter binds the recorded success marker to its manifest, checksums list, and listed artifact hashes before setting certification. The interface does not claim to independently rerun biological validation. Failed and incomplete runs remain visible with their original states.

## Features

- Overview with sample call rates and explicit stage-specific denominators.
- Run search, status filters, synthetic-data toggle, and run selection.
- Sample inspection and CSV export.
- VCF audit ledger with actual depth, genotype quality, source FILTER, and decisions.
- Side-by-side recorded policy comparison; choosing a policy does not execute a workflow.
- Source hashes, original revision/dirty state, task trace and source artifact links.
- Recorded cloud execution and cost estimates, with billing and validation limitations.
- Downloadable run JSON and full snapshot. Imported schema-version-1 snapshots are read locally; the UI labels their certification claims as supplied, not reverified.

Re-export after generating new reports. Extend `DEFAULT_RUNS` in the exporter to include additional recorded run directories. Bundled paths reflect historical runs and are not assumed to be current pipeline outputs.

## Verify dashboard changes

```bash
python3 -m unittest discover -s dashboard/tests -p 'test_*.py'
node --test dashboard/tests/logic.test.mjs
node --check dashboard/app.js
```

Dashboard code does not change the scientific workflow, launch jobs, upload files, or query an AWS account. Imported snapshot data remains only in browser memory until refreshed or closed. Source artifact links point to the public GitHub repository; the dashboard does not embed or execute arbitrary report HTML.

## Public static hosting

See [AWS hosting instructions](../infra/dashboard/README.md) for the allowlisted build, Free-plan verification, updates, cost assumptions and scoped teardown. `make -f dashboard/Makefile dashboard-publish` prepares production assets without any cloud calls. No pipeline or backend is involved.
