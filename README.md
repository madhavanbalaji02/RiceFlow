# RiceFlow

CPU-only, Nextflow DSL2 rice genomics QC with Python, PLINK 2, BCFtools/HTSlib, SAMtools and Docker.
Built as a workflow-engineering portfolio project. Two scientifically distinct tracks share a report:
filtered/pruned public CoreSNP cohort QC, and individual-accession regional VCF DP/GQ processing.
They are never merged into a fabricated joint-called cohort.

```bash
make setup                  # uv + Java 17.0.20 required; pins in config/toolchain.yaml
make test                   # tiny synthetic, hand-calculated fixtures
make workflow-test          # nf-test integration
make recovery               # failure → resume → policy-change invalidation assertions
make demo                   # new run-specific report directory
make preflight              # bounded public retrieval; exits 2 when any gate is blocked
make real-demo              # real CoreSNP; reference-dependent VCF track explicitly BLOCKED
make container              # local linux/amd64 Docker build; no push
make cloud-validate         # Terraform init/validate only; no AWS credentials
```

Start with [dataset evidence](DATASET_VALIDATION.md), the [runbook](docs/RUNBOOK.md),
[scientific assumptions](docs/SCIENTIFIC_ASSUMPTIONS.md), [metric definitions](docs/DATA_DICTIONARY.md)
and [architecture](docs/ARCHITECTURE.md). The [interview explanation](docs/INTERVIEW.md) describes the
engineering decisions and scientific limits. [AWS preparation](docs/AWS_RUNBOOK.md) and
[cost planning](docs/COST_ESTIMATE.md) are separate from local execution.

Verified real cohort: 3,024 samples, 404,388 loci, complete compressed/decompressed SHA256 and binary
validation. Demonstration: first 24 lexical FID/IID pairs, chr1:1–1,000,000; 969 selected loci, 824 retained,
24 retained samples under sample call rate 0.8/site call rate 0.9. This is downstream QC of already
filtered and LD-pruned data, not reproduction of original variant discovery.

Indexed B001 retrieval confirms a 2,187,654,873-byte source, single sample, chr01-style contigs,
reference and nonreference records, and mixed per-record FORMAT fields. Matching authoritative
IRGSP-1.0 FASTA retrieval is blocked by TLS certificate-chain verification at RAP-DB. No real VCF
reference-base or DP/GQ QC validation is claimed. Synthetic VCF/FASTA fixtures exercise those checks.
See [recorded validation](docs/VALIDATION_RESULTS.md) for actual tests, commands and execution limits.

Outputs include self-contained HTML, TSV/Parquet, JSON metrics, unfiltered/filtered native PLINK,
masked/filtered indexed VCF, exclusions, sensitivity comparisons, source/output checksums,
run manifests and Nextflow trace/timeline/execution reports. Require `SUCCESS.json`; HTML alone is
not success. Incomplete real-data reports remain clearly marked. Empty denominators stay null.

Default local budget: 4 CPUs/8 GB scheduler memory, concurrency two with one thread per tool.
AWS is CPU Batch with no provisioned resources. USD 15/month is a planning target, not a hard cap;
cloud deployment, upload and execution require explicit authorization and a fresh cost estimate.
Imputation, haplotype expansion and pangenome construction are outside this release.

Deliverable reports in this workspace: [synthetic](reports/deliverable-synthetic/report.html) (SUCCESS)
and [real cohort](reports/deliverable-real-cohort/report.html) (INCOMPLETE: VCF reference gate blocked).
The [machine-readable validation index](reports/validation-summary.json) links the executed evidence.
