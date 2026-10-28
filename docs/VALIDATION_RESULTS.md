# Executed validation — follow-up audit, 2026-10-27

Current state: **both required real-data tracks pass**. The reference access blocker was resolved
using RAP-DB's current official NARO HTTPS hostname. Historical deliverable reports and scientific
files remain unchanged; their original blocked statuses were valid when generated. The previous
machine-readable index is preserved as `reports/audit-20261027/previous-validation-summary.json`.

Current index: [reports/validation-summary.json](../reports/validation-summary.json).
Exact arguments, UTC times, exit codes, total wall time and OS memory measurements are recorded in
[commands.jsonl](../reports/audit-20261027/commands.jsonl). Failed development checks remain visible;
final passing checks are named explicitly below. Current runs record commit a1560f8 plus dirty state
and actual source hashes, rather than claiming this uncommitted audit was already published.

| Executed command/check | Observed result and evidence |
|---|---|
| Baseline `make test workflow-test` before edits | Existing 28 native tests and one nf-test passed; baseline-tests.log |
| Final `make test workflow-test` | **44 passed, no skips**, one nf-test pipeline test passed; code-cache-tests.log |
| Final image `python -m pytest -q` | **44 passed, no skips** inside linux/amd64 Docker; verified-container-tests.log |
| `make lint` | Ruff and Terraform formatting passed; audit-script-lint.log |
| `make cloud-validate` | Backend-disabled init and provider-schema validation passed; terraform-validation.log; no cloud state/resource creation |
| Initial new preflight | Cached cohort identities/gzip CRC passed; authoritative reference publisher checksum and 10,001 observed REF alleles passed; preflight.log/source-manifest.json |
| Cache-reuse preflight | Exit 0 under **1 MiB full** budget; all three cohort files and full FASTA reused, 341,320 full / 423,473 regional bytes transferred; cache-reuse-preflight.log |
| Clean synthetic run | Exit 0, both tracks PASS, SUCCESS marker; verified-synthetic/ |
| New real two-track Docker run | Exit 0, cohort PASS and VCF PASS, SUCCESS marker; verified-real/ |
| Named real GQ40 native run | Exit 0, both tracks PASS, six SNP sites retained; verified-gq40/ |
| Explicit cohort-only run | Launcher exit 1, cohort PASS / VCF BLOCKED, overall INCOMPLETE, no success marker; final-native-cohort-only/ |
| Controlled failure and UUID resume | Failed COLLECT exit 42 (Nextflow/launcher exit 1), then resume exit 0 with exactly two CACHED scientific tasks; recovery-479558bf/ |
| DP choice change | Exit 0, no cached tasks, different analysis fingerprint; same recovery directory |
| Actual Python source-comment change | Exit 0, no cached tasks with unchanged biological policy; semantic outputs identical; source bytes restored afterward |
| Repeated real Docker analysis | Exit 0; same analysis fingerprint, **31 biological artifact comparisons equivalent**; verified-real-repeat/ and verified-semantic.json |
| Independent standard-tool checks | Standalone container BCFtools queried source/output GT, DP, GQ and FILTER; all 969 baseline/824 final PLINK allele-count rows reconciled; verified-independent.json |
| Independent REF checking | Standalone BCFtools `norm -f reference.fa -c e` accepted all 10,001 records; verified-reference-check.log |
| Marker/file/schema audit | Four certified new runs revalidated: 79 synthetic and 80 files per real run; actual indexed records and regenerated genotype metrics checked; final-artifact-verification.json |
| HTML verification | Embedded Plotly charts, explicit denominator/selection interpretation, no external script/CSS dependency; no visual browser inspection claimed |
| Existing GitHub Actions | The published a1560f8 run succeeded: [40560762699](https://github.com/madhavanbalaji02/RiceFlow/actions/runs/40560762699). New uncommitted audit changes have only local evidence, not a hosted CI claim |

All paths in the table are under `reports/audit-20261027/`. Unit network fixtures exercise local refusal
and indexing cases; they do not stand in for real TLS, publisher-reference or public-data validation.
Native development uses explicitly identified pysam-compiled BCFtools/SAMtools adapters. The Docker
workflow and independent real checks execute standalone PLINK 2, BCFtools and SAMtools binaries.

## Real cohort evidence

The reused full files match all prior compressed/decompressed SHA256 values and valid gzip streams.
Validation independently recounted 3,024 unique samples and 404,388 loci and rechecked the SNP-major BED
size 305,717,331 bytes. The first 24 lexical samples are B001–B021, B023, B024 and B025; B022 is absent.
Earlier prose saying “B001 through B024” was wrong, but archived selection files already held the
correct identities. New analysis reconfirmed chr1:1–1,000,000 inclusive contains 969 selected loci;
all 24 samples and 824 loci remain at sample/site call-rate choices 0.8/0.9. The 145 site exclusions
are reported with explicit reasons and stage denominators. There was no sample exclusion in this
real subset; the effect of sample exclusion on recomputed site rates is proved by hand-calculated fixtures.

The input remains already filtered and LD-pruned. Native PLINK A1 counts are not independently oriented
REF/ALT counts. No reference-validated cohort VCF, original variant discovery, HWE analysis, DP/GQ
values for BED inputs, imputation or population-wide result is claimed.

## Reference and real VCF evidence

The old endpoint's observed TLS chain includes an untrusted Fortinet appliance CA. The same default
trust store and clock verify the current official `rapdb.dna.naro.go.jp` endpoint. This identifies the
observed network-path trust failure, without claiming the publisher's origin certificate itself is
invalid. No insecure fallback, disabled hostname/certificate check, arbitrary root or system trust
change was used. The TLS diagnosis is retained separately.

The exact IRGSP-1.0 FASTA named by the original project README was downloaded after size discovery:
121,184,922 compressed bytes, publisher MD5 `5c5750e0d06b54b7360b35be73aef3de` verified, local SHA256
for compressed/decompressed bytes recorded. Its uncompressed SHA256 is
`c60dd24591bc151eb2c9253a4c8ffbef3f9e50a69e7e3ddb905209087f16467b`.
All 12 declared contig names/lengths and all observed REF alleles match; no alias map or allele rewrite
was required. MD5 is the publisher integrity check, not a replacement for SHA256 or verified transport.

B001 chr01:1000000–1010000 has exactly 10,001 observed diploid records: 9,994 reference-only records and
seven heterozygous biallelic SNPs. The original 339,302-byte index was used for regional access; the
2,187,654,873-byte VCF was never fully downloaded and has no claimed full SHA256. The header records
upstream UnifiedGenotyper in EMIT_ALL_SITES mode; this workflow does not rerun that discovery pipeline.

Actual formats mix GT:DP with GT:AD:DP:GQ:PL. All seven SNPs carry DP25–39/GQ34–99; the reference records
lack GQ. The default DP5/GQ-disabled policy assesses seven SNPs with zero failed/unassessed SNP-quality
calls and retains all seven. GQ40 separately masks chr01:1001391 (GQ34): seven assessed SNPs, one failed,
zero unassessed, six complete calls after masking. The sample passes at 6/7; site filtering then retains
six sites. Final 6/6 completeness is a selection result using a different denominator, not improved
biological accuracy. Reference records are preserved separately, and source LowQual labels remain
unchanged, including labels on retained records. DP30 sensitivity masks the DP25 call without changing
other policy choices. A second accession was unnecessary to establish these gates.

Independent BCFtools GT text and PLINK tables reproduce the reported counts. Masked no-calls have
AN0 and unavailable frequency, not fabricated AF0 or 0/0. Scope, failed quality, not-assessed quality,
missing/partial GT and site/sample exclusions are separate, reconciled categories.

## Correctness and recovery fixes

The new real gate binds the actual VCF identity, sample, index, interval and reference to preflight.
Finalization independently verifies JSON/Parquet/TSV values and empty schemas, native BED-derived and
indexed VCF-derived metrics, scope/quality accounting and trace process/status/exit/attempt fields.
Invalid artifacts or malformed traces cannot publish success. JSON certification is atomic; stale
markers are removed during failed internal finalization, while the launcher refuses existing run paths.

Native tasks now consume actual source-code hashes as cache inputs. An installed editable Python change
previously could leave native task cache keys unchanged. A temporary comment probe now forces both
scientific tasks to rerun with the same biological policy and yields identical biological outputs;
the original source is restored in a guarded finally block. Parameter changes likewise invalidate
results. Unchanged resume preserves the analysis fingerprint and reuses the two completed tasks.

## Measured resources and practical limits

| Final invocation | Whole command wall time | OS wait4 host peak RSS |
|---|---:|---:|
| Native synthetic | 4.434 s | 355,811,328 bytes |
| Real Docker | 10.676 s | 325,402,624 bytes |
| Repeated real Docker | 10.803 s | 333,217,792 bytes |
| Native real GQ40 | 6.149 s | 382,812,160 bytes |

These wall times include the complete launcher invocation, source/image checks, Nextflow and final
Python report/artifact validation. Setup/build/downloads are separate. The earlier manifest field
elapsed_seconds measures Nextflow duration only. Host RSS is the OS process-tree high-water measurement,
not summed concurrent RSS and not Docker VM memory. The real Docker task trace separately reports
COHORT_QC 4.6 s / 311.8 MB peak RSS and VCF_QC 4.0 s / 102.2 MB peak RSS. Trace sampling can miss short
peaks; tiny-task zeros do not establish no memory use. Native macOS lacks per-task trace RSS.

Retain the conservative 4-CPU/8-GB local envelope and 2-GB task requests. Apple Silicon amd64 emulation,
one small interval and 24 selected cohort samples do not establish AWS or population-scale performance.
The first new preflight transferred 121,526,242 full / 423,473 regional bytes; a reuse preflight
transferred 341,320 / 423,473 bytes. Known historical plus new genomic payloads remain below the original
500 MiB full / 16 MiB regional limits. Software/container and public pricing metadata are separate.

## Cloud boundary at the earlier audit

Existing Terraform was validated locally with backend initialization disabled; no cloud state files,
resources, S3/ECR uploads or jobs were created. No new infrastructure was added. Public current AWS
price feeds support the explicit ~$4.56/month planning scenario in COST_ESTIMATE.md; actual account
usage, remaining allowance, cloud runtime, IAM/network behavior, shutdown/scale-to-zero and cloud resume
remain unmeasured/unexecuted. Explicit deployment/upload/workload authorization, fresh usage/cost
review and a user-provided budget email remain mandatory. Budget notifications remain delayed alerts,
not hard caps. The local scientific reference blocker is resolved.


## Authorized AWS follow-up — 2026-10-27

The subsequently authorized Ohio demonstration now passes both scientific tracks. The user confirmed
existing account charges were unrelated and approved up to $5 additional. The Project allocation tag
was activated and the $15 pre-tax/pre-credit budget and $5/$10/$15 notifications were verified live.
See `reports/aws-demo-20261027-summary.json` for current shutdown status and source/image hashes.

The real cloud workflow completed in 262.544 seconds including queue and cold worker startup. All
three Batch jobs succeeded once, with no automatic retries. Artifact revalidation checked 80 files,
JSON/TSV/Parquet metrics, native BED genotypes, indexed VCFs, source binding and self-contained HTML.
All 31 biological comparisons against the current-source Docker run were equivalent. The cohort
retained 24 samples/824 loci; the VCF retained seven SNPs and 9,994 reference records separately.
Trace biological command measurements were COHORT_QC 3 s / 284.8 MB peak RSS and VCF_QC 5.4 s /
85.5 MB. Job/queue duration includes staging and startup; sampled RSS is not whole-host memory.
COLLECT's 4 ms / zero RSS does not establish zero memory use. No population-scale claim follows.

The first attempt failed because controller `git` was absent; the second failed on the observed
`batch:TagResource` denial. Neither submitted a job or launched workers, and both controllers stopped
with zero workers. The missing-executable provenance path now has a regression test; bootstrap installs
git. The corrected IAM policy permits tagging Nextflow definitions/jobs. A reviewed Terraform plan
also prevented a spurious replacement when a stopped controller released its ephemeral public IP;
that expected state change is now ignored, preserving the controller disk/cache.

Final-source checks passed 47 native tests, 47 container tests, one nf-test, Ruff and a new Docker real
run (12.226 s OS-measured command wall time; 327,647,232 bytes host process-tree high-water RSS). That
run revalidated all 80 artifacts and also matched the earlier audit's 31 comparisons. Logs and the
source-matched local run are preserved under `reports/audit-20261027/cloud-follow-up-local/`.
The original audit snapshots are historical and were not rewritten to claim the later source.

Scientific workers use the source-attested immutable amd64 ECR image and pinned scientific tools.
The AL2023 controller actually used Python 3.11.17 and Corretto 17.0.21, rather than the local Python
3.11.14/Java 17.0.20 patches. Nextflow 25.10.2 and locked Python libraries were unchanged. Its exact
versions are recorded; the OS bootstrap does not establish bit-identical future distribution packages.
Raw cloud resource/billing responses and full controller artifacts remain local under
`reports/aws-demo-20261027/`; the public summary omits credentials and account-wide billing details.
Cloud restore/exact-UUID resume after completed tasks remains unexecuted. Existing local controlled
failure/resume, policy invalidation and source invalidation evidence remains valid for its snapshots.


Final shutdown verification: the controller is stopped, the worker terminated, Batch desired vCPUs
returned to zero, and the direct cleanup receipt reports returncode 0 with no jobs, workers or backup
errors. Final inventory retains one 16 GB gp3 controller volume, 297 S3 objects totaling 1,044,514,357
bytes and two immutable image versions. Referenced tagged-image sizes sum to 724,644,346 bytes;
shared layers mean this is not an exact deduplicated ECR bill. The conservative observed runtime
bounds are 0.3936 aggregate controller-hours and 0.1578 worker-hours. Applying verified rates, a full
month of retained storage, the baseline request/log/transfer reserves and 10% contingency gives a
$1.84 scenario, within the approved additional $5. Retained storage alone is estimated at $1.38/full
month until authorized cleanup. The broader 20-hour monthly planning scenario remains $4.59.

SSM's final delivery receipt did not report command success. Scientific success and cleanup are
established independently by validated artifacts, three zero-exit Batch jobs, the direct cleanup
receipt and stopped/zero resource observations. Do not substitute SSM transport status for those
checks. Billing still shows an estimated zero for the project tag; posting/allocation delays mean
that is not a final invoice or proof of zero cost.


## Linux Docker publication correction

Hosted CI for f8a3d83 passed the native job and all 47 container Python tests, then exposed a Linux
publication failure after all Nextflow tasks exited zero. Atomic JSON files had tempfile's mode 600
and belonged to container root, so the runner could not copy summary JSON files into reports. The
launcher correctly withheld SUCCESS and marked the mandatory tracks incomplete; passing task exits
were insufficient. This was not a scientific calculation failure.

Atomic report JSON now becomes mode 644 before rename, preserving atomicity while allowing host
publication. A regression checks report readability; a direct Linux test writes as root and reads
as UID 65534. Both native/container suites now pass 48 tests, nf-test passes once, and new real and
synthetic Docker workflows pass artifact validation. All 31 biological comparisons between corrected
real outputs and the earlier cloud run are equivalent. New real command wall time was 11.890 seconds
and host process-tree high-water RSS 370,245,632 bytes; synthetic command wall time was 6.431 seconds.

Evidence is preserved under `reports/audit-20261027/linux-publication-follow-up/`, including the
original hosted failure log. The cloud source/image snapshot remains unchanged: it completed before
this permission correction, and cloud S3 transfers do not preserve those POSIX file modes. Credentials
and deployment state remain excluded from Git. Release metadata now acknowledges the published ECR
audit images; scientific version pins did not change. Later hosted CI is verified after pushing this
correction; this report is the frozen evidence captured before that push.
