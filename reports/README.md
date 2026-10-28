# Recorded validation evidence

These are historical artifacts from the local 2026-10-27 implementation and validation session.
Their manifests correctly record that the workspace had no Git repository when those runs occurred;
the later initial source commit does not retroactively change that provenance.

- `deliverable-synthetic/`: certified synthetic two-track run, with SUCCESS.json.
- `deliverable-real-cohort/`: verified cohort results; overall INCOMPLETE because real VCF reference access was blocked.
- `recovery-09cab55b/`: intentional failure, UUID-based resume with two cached tasks, and policy-change invalidation.
- `real-demo-final/`: native run associated with the recorded macOS resource measurement.
- `data-evidence/`: source manifests, official metadata/usage statements and small regional VCF extracts.
- `validation-summary.json`: machine-readable evidence index.

Generated run artifacts retain their original checksums and local paths. Downloaded full inputs,
Nextflow work/cache files, installed tools and intermediate development runs remain local and are
excluded from Git. Reproduce new runs using the repository's make targets. See
`../docs/VALIDATION_RESULTS.md` for interpretation and limitations.

The follow-up `audit-20261027/` contains newly executed two-track real-data validation after resolving
the official reference hostname, plus independent checks, source-aware recovery, semantic comparisons,
current public price evidence and a complete command/exit/resource ledger. Current entries are indexed
by validation-summary.json; prior reports retain their historical statuses and checksums.


The authorized Ohio follow-up is indexed by `aws-demo-20261027-summary.json`. Both cloud tracks passed,
80 artifact hashes and 31 biological comparisons validated, and compute stopped with zero workers.
Current-source local evidence (47 native/47 container tests, one nf-test, source-matched real Docker
run and comparisons) is under `audit-20261027/cloud-follow-up-local/`. Full cloud reports/resource
responses remain local and ignored under `aws-demo-20261027/`; the public summary omits credentials
and account-wide billing. Earlier audit snapshots retain their original source identities.

The subsequent Linux JSON publication fix and current 48-test evidence are in `audit-20261027/linux-publication-follow-up/`; the original cloud snapshot and prior CI failure remain separate.
