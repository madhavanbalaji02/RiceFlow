# AWS execution, recovery and shutdown

The explicitly authorized 2026-10-27 Ohio (`us-east-2`) real-data demonstration passed both tracks.
All three Batch jobs exited zero, all 80 artifact hashes validated, and 31 biological comparisons
matched the source-matched local Docker run. Workflow wall time was 262.544 seconds including queue
and cold worker startup. See [the execution summary](../reports/aws-demo-20261027-summary.json) for
current shutdown status, exact source/image hashes, trace measurements and remaining unexecuted gates.
Final verification confirms the controller stopped, the worker terminated and Batch desired vCPUs zero. The cleanup receipt reports exit 0, no jobs/workers and no backup errors. Raw account responses and complete cloud reports remain local under `reports/aws-demo-20261027/`.

The user confirmed prior account charges were unrelated and approved up to $5 additional. The Project
cost tag is active. The deployed $15 budget excludes taxes, credits and refunds, with actual-cost
notifications at $5/$10/$15 to the user-supplied recipient. Notifications and billing are delayed;
neither the budget nor resource limits enforce a hard dollar cap. Review COST_ESTIMATE.md before reuse.

Two earlier attempts failed before job submission: absent controller git, then missing
`batch:TagResource`. Both stopped with zero workers. Bootstrap now installs git, provenance collection
handles an unavailable executable, and the controller can tag Nextflow definitions/jobs. Terraform
ignores the expected loss of an ephemeral public IP while stopped, preserving the controller disk
rather than proposing replacement. IAM edits were reviewed as a single policy update before apply.

## Reproduce only after fresh specific cost authorization

1. Verify cached scientific inputs using preflight; preserve its source manifest and publisher/local
   checksums. Keep the native cohort and accession VCF separate. Review fresh project usage, retained
   storage, aggregate worker/controller hours, prices and the proposed run. Require
   `conservative_run + observed_month + retained_month <= 15` and hours within 20 each; also respect
   the user's smaller approved incremental allowance. Unknown prior usage requires classification
   or specific revised approval. Authorization expires after 24 hours in the existing runtime gate.
2. Put Terraform variables in an ignored private file, including the reviewed region, bucket name,
   user-provided budget email, x86_64 AL2023 AMI and max vCPUs=2. Review a saved plan before applying.
   The existing module creates the public subnet/IGW, outbound-only security group, private SSE-S3
   bucket, immutable ECR repository, seven-day logs, CPU Batch environment/queue, roles and controller.
   No NAT, load balancer, paid interface endpoint or database is used. Apply starts billable compute.
3. Build/test the amd64 CPU image and verify its Python source against the intended source snapshot.
   Push an immutable release tag and record ECR's `@sha256` RepoDigest, not a local image ID. The
   executed release's digest is in the summary. Upload the attested cohort BED/BIM/FAM, regional B001
   VCF, exact reference FASTA and FAI to `inputs/` and `reference/`. This demonstration uploaded cached
   local files; it did not download the complete multi-gigabyte VCF. S3 validated supplied SHA256
   checksums during PUT; scientific tasks rehashed their staged inputs before processing.
4. Prepare a controller archive containing the reviewed `src/`, `modules/`, `workflows/`, `conf/`,
   `scripts/`, configuration, `pyproject.toml`, `requirements.lock`, `nextflow.config`, pinned Nextflow
   executable/plugin cache and Linux PLINK executable. Include the verified source manifest as
   `source-manifest.json`, the complete reviewed per-run cost authorization as
   `cloud-authorization.json`, and `config/aws-demo.yaml`. Its cohort/VCF/reference paths must be S3
   URIs, `input_sha256` must contain all attested input digests, and source_manifest must reference
   the archive's local copy. Keep the original policy, selection and region. Exclude `.env`, Git,
   credentials, Terraform state, private sessions and unrelated data. Upload and record the archive
   SHA256. The three executed archive identities are retained in local upload receipts.
5. Use SSM with the controller's instance profile; no SSH ingress or long-lived credentials are
   copied. From `/opt/riceflow-controller`, set `AWS_DEFAULT_REGION`/`AWS_REGION` consistently with
   Terraform, and set `RICEFLOW_PACKAGE_URI`, `RICEFLOW_PACKAGE_SHA256`, `RICEFLOW_QUEUE`,
   `RICEFLOW_S3`, `RICEFLOW_IMAGE`, `RICEFLOW_TASK_ROLE`, `RICEFLOW_LOG_GROUP`, and
   `RICEFLOW_CONTROLLER_ID`. Set a new `RICEFLOW_OUTDIR` for every attempt. Download the archive,
   verify SHA256, extract it and run `scripts/bootstrap-controller.sh` from the extracted project.
   The bootstrap verifies the archive, installs the controller runtime/libraries, and invokes
   `scripts/cloud-controller.py` around the actual `riceflow run --profile aws` command.
6. Scientific tasks use the pinned image. The executed AL2023 controller used Python 3.11.17 and
   Corretto 17.0.21; these differ from local 3.11.14/17.0.20 patches and are recorded honestly.
   Nextflow 25.10.2 and locked Python libraries were preserved. Distribution package installation
   is not a claim of a bit-identical future OS bootstrap. The source archive and immutable task
   image provide independent code identities.
7. Watch the dedicated queue externally. One submitted job at a time, one CPU/task, no automatic
   retries, 15-minute task bounds and the bootstrap's 900-second overall workflow deadline keep
   the small demonstration bounded including queue wait. The controller wrapper defaults to
   1,800 seconds and refuses larger values. Bootstrap/cleanup time and idle workers also cost money.
   Neither a local finally block nor a shell deadline survives every failure; the external operator
   must verify cleanup and react to lost connectivity or nonterminal jobs.
8. After Nextflow returns, the launcher validates outputs before SUCCESS. The wrapper cancels queued
   jobs or terminates running jobs on failure, waits for terminal status, syncs reports and
   `.nextflow/` (including history/cache), then waits up to ten minutes for zero active workers.
   It records `cloud-controller-status.json` and stops via OS shutdown only after jobs and workers
   are verified terminal/zero. If verification fails, it retains the controller for external recovery.
   A shutdown-interrupted SSM command is not the scientific status; use the validated run manifest
   and success marker. Verify controller stopped, workers zero and the final resource inventory.

## Inspection and recovery

Use the reviewed region consistently in these commands:

```bash
aws batch describe-compute-environments --compute-environments "$RICEFLOW_COMPUTE_ENV"
aws batch list-jobs --job-queue "$RICEFLOW_QUEUE" --job-status RUNNING
aws batch list-jobs --job-queue "$RICEFLOW_QUEUE" --job-status RUNNABLE
aws batch describe-jobs --jobs <recorded-job-ids>
aws ec2 describe-instances --filters Name=tag:Project,Values=RiceFlow
aws ec2 describe-volumes --filters Name=tag:Project,Values=RiceFlow
aws ec2 describe-addresses
aws s3 ls "$RICEFLOW_S3/work/" --recursive --summarize
aws ecr describe-images --repository-name riceflow-demo
aws logs describe-log-groups --log-group-name-prefix /aws/batch/riceflow-demo
```

After an abrupt controller failure, enumerate ALL active statuses: SUBMITTED/PENDING/RUNNABLE/STARTING/
RUNNING. Cancel queued jobs and terminate started jobs only in this dedicated authorized run, verify
all recorded jobs terminal, and inspect managed workers before stopping the controller. Example:

```bash
aws batch cancel-job --job-id <queued-id> --reason 'authorized run cancellation'
aws batch terminate-job --job-id <started-id> --reason 'authorized run cancellation'
# Only after jobs terminal and workers zero:
aws ec2 stop-instances --instance-ids <controller-id>
aws ec2 wait instance-stopped --instance-ids <controller-id>
```

The 16 GB encrypted controller root disk persists after stop and has delete-on-termination disabled;
it continues billing. Worker 30 GB encrypted gp3 disks delete on termination. ECR keeps immutable
releases; untagged images expire after seven days. Work and controller backups expire after 30 days;
scientific inputs/reference/results have no automatic expiration. Preserve the resume window and
all scientific outputs. Separate teardown authorization is required before destructive cleanup; the
bucket has `prevent_destroy` and is not force-deleted. Inspect snapshots, disks, IPs, S3/ECR and logs
rather than assuming compute shutdown removes storage costs.

Executed evidence establishes one two-track cloud run and its artifact equivalence. A controlled
failure after completed cloud tasks, exact-UUID cloud resume/restore and later invoice reconciliation
remain unexecuted gates. Local failure/resume and policy/source cache invalidation were demonstrated
separately; do not substitute them for cloud evidence. The cloud summary records shutdown independently.

The AWS profile uses `aws.batch.jobRole`/`logsGroup`; the task image supplies AWS CLI, so no host
`cliPath` mount is configured. These settings follow the [Nextflow AWS configuration documentation](https://docs.seqera.io/nextflow/reference/config/aws)
and [Batch executor documentation](https://docs.seqera.io/nextflow/reference/executor/aws-batch).
