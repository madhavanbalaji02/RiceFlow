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
