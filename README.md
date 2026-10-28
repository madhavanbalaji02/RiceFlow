# RiceFlow

CPU-only Nextflow DSL2 rice QC with Python, PLINK 2, BCFtools/HTSlib, SAMtools and Docker. The existing
architecture keeps the already filtered/pruned CoreSNP cohort separate from individual-accession VCF
quality processing. The summaries share a report; the inputs never become an invented joint-called cohort.

The 2026-10-27 follow-up audit resolved reference access through RAP-DB's current official NARO HTTPS
hostname, verified the publisher checksum and all observed REF bases, and completed the real VCF track.
The [dataset evidence](DATASET_VALIDATION.md) explains the TLS diagnosis and exact assembly identity.

```bash
make setup                         # project-local pinned tools; Java 17.0.20 and uv required
make test workflow-test             # offline fixtures plus nf-test
make recovery                       # synthetic failure → UUID resume → policy invalidation
make preflight                      # new timestamped outputs; verify/reuse available attested caches
make demo                           # new synthetic two-track report
make real-demo                      # recorded local real config: both tracks now required
make lint cloud-validate             # local checks; Terraform backend disabled, no deployment
```

For a fresh checkout, run preflight and use its generated configuration, rather than assuming this
machine's cached paths exist:

```bash
make preflight PREFLIGHT_OUT=data/my-preflight
PATH="$PWD/.venv/bin:$PWD/.tools:$PATH" NXF_HOME="$PWD/.tools/nxf-home" \
  riceflow run --config data/my-preflight/run-config.yaml
```

When caches exist, preflight verifies compressed/decompressed SHA256 and gzip integrity before reuse.
It discovers remote sizes, enforces 500 MiB full/16 MiB regional payload defaults, and refuses servers
that ignore Range. No full multi-gigabyte VCF is downloaded. Preflight outputs and run paths must be new.
A repeated preflight reused the full cohort and reference under a 1 MiB full-transfer budget.

The verified cohort has 3,024 samples and 404,388 loci. Its deterministic demo selects B001–B021,
B023, B024 and B025, chr1:1–1,000,000 inclusive: 969 loci selected, 824 retained, all 24 samples retained
at sample/site call-rate choices 0.8/0.9. B022 is absent; earlier prose describing B001–B024 was wrong.
This is downstream QC of already filtered, LD-pruned data, not raw variant discovery.

B001 chr01:1000000–1010000 has 10,001 observed records: seven biallelic SNPs and 9,994 explicit reference
records. All observed REF bases match publisher-verified IRGSP-1.0; no contig aliases or allele swaps
were needed. Default DP≥5 with GQ disabled retains all seven SNPs. The separately named
[REAL_GQ40 policy](config/real-gq40.yaml) masks one call, assesses the sample at 6/7 SNPs, then retains
six sites. Increased completeness among retained sites is selection, not evidence of improved accuracy.

Outputs include masked/filtered indexed SNP VCFs, separate indexed reference/unsupported record files,
native PLINK subsets, TSV/Parquet/JSON metrics, scope/exclusion accounting, one-threshold sensitivity,
self-contained HTML and Nextflow execution/trace/timeline reports. The launcher independently checks
artifacts and source identity before atomic SUCCESS.json publication. Track status and overall status
are separate. Failed or incomplete runs cannot inherit an old success marker. Empty denominators stay null.

Docker builds remain linux/amd64 CPU-only; Apple Silicon uses emulation or native development adapters.
Run `make container`, then `riceflow run --profile docker` with the PATH/NXF_HOME above. The launcher
resolves the image ID and checks its Python source against the workspace to reject stale images.
The audit also uses an explicit `riceflow:audit-20261027` image; its actual digest is recorded in the
new run manifests and audit index. Historical image IDs and reports remain intact.

See [validation results](docs/VALIDATION_RESULTS.md), [runbook](docs/RUNBOOK.md),
[scientific assumptions](docs/SCIENTIFIC_ASSUMPTIONS.md), [metric dictionary](docs/DATA_DICTIONARY.md),
[architecture](docs/ARCHITECTURE.md) and [interview explanation](docs/INTERVIEW.md).
[Current evidence index](reports/validation-summary.json) links all new runs under reports/audit-20261027/;
older deliverable reports remain archived with their original statuses and checksums.

Local scheduling stays within 4 CPUs/8 GB, concurrency two and one thread per tool. The explicitly
authorized Ohio AWS demonstration passed both real tracks in 262.5 seconds including queue/startup;
all 80 artifact hashes validated and 31 biological comparisons matched the same-source local run.
The [cloud summary](reports/aws-demo-20261027-summary.json) records current shutdown status and the
two earlier failures before job submission. Current-source checks passed 48 native tests, 48 container
tests, a direct cross-UID Linux publication check and one nf-test integration test. Earlier 44/47-test
snapshots remain preserved. The later publication fix changes JSON file modes; 31 biological comparisons
with the original successful cloud run remain equivalent.

See the [AWS runbook](docs/AWS_RUNBOOK.md) and [itemized estimate](docs/COST_ESTIMATE.md). The user
approved up to $5 additional; the $15/month project target remains a planning target, not a hard cap.
The Project cost tag is active and $5/$10/$15 alerts are configured. Subsequent runs still require
fresh cost/hour evidence and specific authorization. Retained EBS, S3, ECR and logs remain billable.
No imputation, haplotype expansion or pangenome construction is included.

## Dashboard

**[Open the public RiceFlow dashboard](https://d35x4x7bn6ghj.cloudfront.net/)** — no sign-in required.

The read-only dashboard explores recorded QC runs, samples, variant decisions, policy comparisons, provenance and historical cloud evidence. SUCCESS, INCOMPLETE and FAILED records remain visible; the cohort and single-accession VCF tracks remain independent. It does not launch jobs or monitor AWS live.

For a local preview, run `make -f dashboard/Makefile dashboard` and open http://localhost:8000. For the exact deployable six-file build, run `make -f dashboard/Makefile dashboard-publish`, then `python3 -m http.server 8765 --directory dist/dashboard`. Run `make -f dashboard/Makefile dashboard-test` for dashboard-specific checks.

See [dashboard features and scientific context](dashboard/README.md) and [AWS deployment, updates, costs and scoped teardown](infra/dashboard/README.md). Hosting uses private S3, signed CloudFront OAC, default-domain HTTPS and an explicitly verified **Free flat-rate subscription**. The subscription costs $0/month; small S3 request charges remain. This is separate from the general AWS Free Tier and does not make the entire account bill zero.
