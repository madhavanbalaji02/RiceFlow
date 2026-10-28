# Local operation and recovery

Requirements: `uv`, Bash, curl, unzip, a Java 17.0.20 installation on PATH, roughly 8 GB available
RAM and 4 CPU cores. `make setup` creates only project-local tools and `.venv`. Native development
uses PLINK 2 ARM on Apple Silicon or x86_64 Linux, and thin explicitly identified adapters to
BCFtools/SAMtools 1.21 compiled into pysam 0.23.3. Production containers compile standalone tools.
No GPU is used. Nextflow controller and Java run on the host.

```bash
make setup
make test
make workflow-test
make recovery
make demo
make preflight        # public network, bounded payload budget; returns 2 if any stage BLOCKED
make real-demo        # uses validated CoreSNP, VCF BLOCKED until compatible FASTA is accessible
make container        # requires Docker running; builds linux/amd64 locally
PATH="$PWD/.venv/bin:$PWD/.tools:$PATH" NXF_HOME="$PWD/.tools/nxf-home" \
  riceflow run --profile docker
```

All launcher runs create a new `reports/<UTC timestamp>-<random suffix>/`. Explicit `--out` paths
must be empty. The configured inputs are relative to the repository working directory. The launcher
writes resolved configuration, input/output SHA256, code hashes, stable analysis fingerprint, actual
tool versions, Git status (null if this workspace has no Git repository), start/end timestamps,
wall-clock elapsed time and task attempts. Identical inputs/settings/code/environment produce the same fingerprint;
run IDs remain unique. File source metadata, source processing and exact subset selections accompany
real runs. Policy changes affect task keys; changing a purely VCF rule conservatively reruns both tracks.

Read `run-manifest.json`, then require `SUCCESS.json`, whose hashes bind the manifest and output
checksum manifest. The launcher validates nonempty final metrics, native BED dimensions, readable
indexed VCF, track status and required Nextflow diagnostics before writing success. HTML alone cannot
establish success. A real cohort run with the VCF reference gate blocked has an INCOMPLETE manifest
and no success marker even when its cohort result passes. This is intentional.

```bash
make resume SESSION=<previous-nextflow-session-name> CONFIG=config/demo.yaml
make report RUN=reports/<run-id> LABEL=SYNTHETIC
```

Prefer the exact session UUID from `nextflow.log` (`Session UUID: ...`). A run name is also accepted,
but concurrent launches in one directory exposed ambiguous name resolution in the tested Nextflow version.
Use UUIDs and avoid simultaneous controllers sharing a launch directory. The recovery script uses UUIDs.
Keep the repository launch directory `.nextflow/cache`, `.nextflow/history`, and `work/` together.
Nextflow needs both metadata and task outputs; preserving only S3 work objects does not establish resume.
Run `make recovery` for an intentional COLLECT exit 42 after both scientific tasks finish, then resume.
The script asserts exactly two CACHED tasks and asserts no reused scientific task after a DP change.
Failures in development evidence remain visible and are not relabeled passing.

A handled failure/timeout writes `failure-manifest.json` after Nextflow returns, regardless of downstream
report tasks. The default 1,800-second controller deadline includes queue wait and kills the process
group on expiration. An abrupt machine/controller death cannot run finalization: a RUNNING manifest
without SUCCESS is interrupted/unknown. Inspect all submitted jobs before restarting; preserve cache,
copy the source run directory for audit, launch a new run with the exact previous session and config.
Never manually create a success marker. Use a persistent controller disk and off-instance metadata
backup for cloud recovery. AWS job cancellation and controller failure are separate concerns.

Troubleshooting: inspect `launcher.log`, `nextflow.log`, `trace.tsv`, and a task's `.command.err` /
`.command.log` under `work/<hash>`. Headers declaring DP/GQ do not imply every record carries them.
A TLS error at RAP-DB is a reference gate failure; do not bypass verification or use the synthetic
FASTA for real data. Once authoritative access works, rerun preflight, supply the verified regional
VCF/FASTA in a REAL config and preserve its source manifest. The default real config deliberately
remains gated; it never silently changes tracks.

Successful run artifacts are immutable. `make report` refuses to overwrite a certified successful
run; use an uncertified copy when regenerating presentation output. The stable analysis fingerprint
also includes the execution profile, resolved image digest, pinned toolchain definition and dependency
lock. A local image digest is recorded in `containers/local-image-id.txt`; rebuilding can change image
bytes as OS package metadata changes. Use the tested content digest for execution rather than assuming
a fresh rebuild is byte-identical. No ECR RepoDigest is claimed for an image that was never pushed.

## Current real-data reproduction and audit

The reference blocker is resolved using the current official NARO hostname. `make preflight` now uses
a new timestamped output directory, reuses available attested caches, and writes run-config.yaml on
success. For a fresh checkout choose `make preflight PREFLIGHT_OUT=data/my-preflight` and then
`riceflow run --config data/my-preflight/run-config.yaml` with the project PATH/NXF_HOME. Existing
cache manifests must match all compressed/decompressed cohort and reference hashes; mismatches fail.
The default full/regional payload budgets remain 500/16 MiB. Cache-reuse validation succeeded with a
1 MiB full budget, demonstrating that the large input files were not fetched again.

This workspace's config/real.yaml selects the verified audit data. config/real-cohort-only.yaml preserves
the historical cohort-only/BLOCKED configuration; config/real-gq40.yaml is a separate named GQ policy.
Run paths must be new. Existing historical reports and success markers remain immutable; an attempted
same-path launch is rejected. Internal finalization revokes a stale marker before any failed status
and atomically publishes JSON after validation. A trace with missing required fields cannot certify.

The audit image is explicitly selected with `--profile docker --image riceflow:audit-20261027`.
The launcher verifies image Python hashes before starting Nextflow; a stale default image must be
rebuilt with make container. Task manifests separately record actual in-container tool versions.

`scripts/record_command.py --ledger <jsonl> --name <unique-name> -- <command...>` records exact arguments,
exit code, UTC times, total wall time and OS wait4 peak RSS. That host process-tree RSS is not the sum
of concurrent task memory and does not include the Docker VM's resident memory. Nextflow trace adds
sampled task RSS/realtime where available; native macOS task RSS remains unavailable.

`scripts/compare_biology.py --first <run> --second <run> --out <json>` compares summaries, all Parquet
metrics, native BED/BIM/FAM bytes and parsed indexed VCF records. It ignores only run metadata, logs,
VCF header command timestamps and compression representation, never genotype/allele/filter differences.
The real recovery demonstration can be rerun using scripts/recovery-demo.py --config config/real.yaml
--root reports/<new-audit-path>. It uses an exact UUID, asserts two cached tasks on resume, changes DP
and checks that affected results are recalculated with a distinct analysis fingerprint.

Native task inputs now include execution_code_fingerprint, calculated from the actual Python/modules/
workflow/config hashes. This prevents resumed native tasks from silently reusing results after an
editable Python source change. The audit's --probe-code recovery test adds one harmless temporary
comment, verifies zero cached tasks and unchanged biological outputs, then restores the original bytes.
Do not edit source or share a controller launch directory while a scientific run is active.

Replay using the original user configuration or the generated preflight run-config.yaml. The expanded
resolved-config.json also carries runtime-only metadata and is not the declared input-schema document.
Use scripts/audit_artifacts.py --run <certified-run> --out <new-audit-json> to revalidate success-marker
bindings, every recorded output SHA256, table values/schemas and genotype-derived metrics. The utility
also checks real-data attestations, code fingerprints and embedded report assets; it does not claim a
visual browser inspection.
