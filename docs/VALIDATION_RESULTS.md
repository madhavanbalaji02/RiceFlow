# Executed validation — 2026-10-27

The workspace began empty, without a Git repository. Manifests accurately record null commit/dirty
state and retain SHA256 hashes for source files. No commit identity is invented.

| Check actually executed | Result / evidence |
|---|---|
| `make setup` | Passed, project-local pinned tools and virtual environment; `reports/setup-validation.log` |
| `make test` | 28 passed, no skips; `reports/final-local-checks.log` |
| `make workflow-test` | nf-test 0.9.3, one end-to-end workflow test passed on Nextflow 25.10.2/Java 17.0.20 |
| `make recovery` | Intentional COLLECT failure, UUID resume with exactly two CACHED tasks; DP policy change yielded zero cached tasks; identical analysis fingerprints on unchanged resume |
| Ruff | Passed; `reports/ruff.log` |
| Docker build and offline fixtures | linux/amd64 image built; 28 passed with standalone PLINK 2 / BCFtools / SAMtools; `reports/final-container-tests.log` |
| Docker synthetic workflow | SUCCESS, all three tasks completed; `reports/deliverable-synthetic/SUCCESS.json` |
| Real-data preflight | Complete cohort verified; indexed VCF retrieval verified; authoritative reference TLS BLOCKED |
| Real cohort Docker workflow | Cohort PASS; report/run INCOMPLETE because VCF reference gate BLOCKED, no success marker |
| Output/report inspection | 75 synthetic and 48 real run file checksums verified; embedded charts, no external script/CSS dependencies; `reports/report-structure-validation.json` |
| Image source audit | Container Python source hashes match workspace exactly; `reports/image-source-checksums.json` |
| Terraform | 1.13.4 init without backend, fmt check, provider 6.19.0 validate passed; provider checksums locked for Linux amd64/macOS arm64 |
| AWS Nextflow profile | Parsed locally; pinned nf-amazon 3.4.1 plugin installed; no AWS job submission |
| GitHub Actions | CI definition prepared; no hosted Actions execution claimed |
| Visual browser QA | BLOCKED: browser runtime reported no available browsers; no screenshot/visual claim |

Read `reports/validation-summary.json` for a compact machine-readable index. The recovery evidence is
`reports/recovery-09cab55b/evidence.json`; it links failure, resumed and parameter-change artifacts.
A concurrent verification run exposed run-name resume resolving the wrong active session in the
Nextflow history. The recovery command now uses the exact logged session UUID and passes. Avoid
concurrent controllers in one launch directory. Earlier development failures remain auditable.

## Scientific real-data evidence

The gzip BED is 117,476,185 bytes. Complete decompression/structure validation found 3,024 samples,
404,388 variants and a 305,717,331-byte SNP-major BED, matching expected dimensions. All three full
source files and their decompressed forms have SHA256 in `reports/data-evidence/source-manifest.json`.
The source is already filtered and LD-pruned; this does not reproduce variant discovery.

The deterministic CoreSNP demo selects lexical FID/IID B001 through B024 and chr1:1–1,000,000 inclusive.
It contains 969 loci. At sample call rate >=0.8 then recomputed site call rate >=0.9, all 24 samples
and 824 loci remain; 145 loci are excluded. Rare variants are not frequency-filtered. Full metrics,
selection, sensitivity comparisons and exclusions are in the cohort directory of the real report.

B001 source size was rechecked via Content-Range: 2,187,654,873 bytes, with a working 339,302-byte TBI.
The first indexed interval chr01:10000–11000 contains 1,001 reference records with GT:DP. A separate
bounded discovery interval chr01:1000000–1001000 contains 1,000 reference records and one heterozygous
SNP record at chr01:1000993 (GT 0/1, DP 39, GQ 46, source FILTER LowQual). It confirms mixed per-record
GT:DP and GT:AD:DP:GQ:PL even though all these fields are declared in the header. These are retrieval
observations, not independently reference-validated scientific QC results.

The official README identifies RAP-DB IRGSP-1.0/MSU7. RAP-DB HTTPS certificate-chain verification failed.
Matching chr01 length alone does not prove identity; no TLS bypass or synthetic reference substitution
was used. Real VCF REF validation and quality analysis remain BLOCKED. Extracts, usage statements,
SHA256 and exact range/byte evidence are preserved in `reports/data-evidence/` and
`reports/additional-region-evidence.json`. No complete multi-gigabyte VCF was downloaded.

## Measurements and their limits

The final local Docker synthetic Nextflow execution measured 5.60 seconds; the real cohort execution
measured 7.44 seconds in the launcher. These exclude setup, downloads, container build, initial version
queries, final Python report generation and checksum finalization. The real COHORT_QC task trace reports
3.4 seconds realtime, 98.0% CPU and 305.8 MB peak RSS. Trace telemetry is sampled and can miss short-lived
peaks; a zero/low value for a tiny task is not proof that no memory was used. Apple Silicon amd64
container behavior is not a cloud runtime benchmark.

A separately measured native real-cohort invocation took 5.48 seconds end-to-end (`/usr/bin/time -l`),
with 359,923,712 bytes maximum resident set size as reported by macOS. Its report is
`reports/real-demo-final/`; native Nextflow did not expose per-task CPU/RSS. These measurements justify
retaining the conservative 4-CPU/8-GB local envelope and 2-GB task requests; no population-scale speed
or memory claim is made.

## Unexecuted cloud work

No AWS resources were provisioned, no ECR images pushed, no S3 inputs uploaded and no cloud jobs run.
Terraform validation is schema/configuration evidence, not a validated deployment. Network/IAM behavior,
cloud report finalization, restore/resume, cancellation, controller shutdown, worker scale-to-zero and
actual costs await a specifically authorized small deployment. COST_ESTIMATE.md requires fresh official
rates, account usage, retained-resource accounting and a user-provided alert email before submission.
