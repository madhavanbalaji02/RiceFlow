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
