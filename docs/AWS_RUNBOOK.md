# Prepared AWS deployment and shutdown procedure

Status: Terraform formatted and provider-schema validated locally. AWS profile/controller code is
prepared but has not been deployed or executed in AWS. IAM/network behavior and shutdown must be
verified in a specifically authorized small demonstration. No cloud performance/cost claim is made.

1. Review COST_ESTIMATE.md, inspect current account usage and retained resources, verify official
   prices and obtain specific user authorization. Obtain a budget email. Use us-east-1.
2. Review an x86_64 AL2023 controller AMI and Terraform plan. The module creates a public subnet,
   IGW, outbound-only security group, private S3 bucket/prefix policies, immutable ECR repository,
   seven-day logs, CPU Batch queue/compute environment, roles, controller, and tagged budget.
3. Only after authorization: apply the reviewed plan. This starts a billable controller. Use SSM,
   no SSH ingress. Install pinned Java/Nextflow and checkout the exact code on its persistent
   root disk; launch from `/opt/riceflow-controller`. Retain `.nextflow`, history and work objects.
4. Only after upload authorization: push the tested amd64 image to ECR and record its `@sha256`
   RepoDigest. Local Docker image IDs are not ECR digests. Upload verified small inputs/reference
   to `inputs/` and `reference/`; preserve source manifest and SHA256 evidence.
5. Use S3 paths for task inputs, work and results. Set RICEFLOW_S3, RICEFLOW_QUEUE,
   RICEFLOW_IMAGE (ECR RepoDigest), RICEFLOW_TASK_ROLE and RICEFLOW_LOG_GROUP from Terraform outputs.
   The prepared config is `conf/aws.config`; `nextflow run workflows/main.nf -c nextflow.config
   -c conf/aws.config` also needs `--config_json`, `--outdir`, and policy/selection parameters.
   Use the dedicated queue for exactly one run. The normal local launcher intentionally exposes
   only native/Docker profiles, so cloud use requires the reviewed controller path.
6. Wrap the reviewed `riceflow run --profile aws` command with `scripts/cloud-controller.py --authorization <file>`.
   Its 1,800-second default deadline includes waiting in the queue. On handled failure it terminates
   remaining queue jobs, waits for terminal status, backs up metadata and stops the controller via
   OS shutdown. Never share this dedicated queue with unrelated jobs. The script has not been cloud
   tested. Its authorization check is an operational aid, not proof of permission or cost enforcement.
7. Inspect jobs, workers and billing externally after each run. The Python launcher finalizes local controller results after Nextflow returns, validates outputs,
   and writes SUCCESS only when required track outputs pass. The controller syncs reports to results/
   before stopping. This prepared S3 path must be integration-tested in the first authorized cloud run.

The controller root volume persists after stop (and has delete-on-termination disabled), so its EBS
continues billing. `t3.small` burst credit behavior requires review and standard credit configuration
before deployment; Terraform uses standard credit mode. No NAT gateway, load balancer, paid interface
endpoint or database exists in the default design. Public IPv4/IGW and outbound network access provide
S3/ECR/Batch/SSM reachability; public IPv4 is billable while allocated. Batch-managed workers use the
ECS-optimized default image. Worker disks delete on termination. Object encryption uses SSE-S3.
Worker min vCPUs=0 does not guarantee instant scale-in; verify actual EC2 state and desired capacity.

Prepared validation commands (read-only/local):

```bash
make cloud-validate
terraform -chdir=infra/terraform fmt -check
```

After a specific deployment is authorized, inspect resources with:

```bash
aws batch describe-compute-environments --compute-environments "$RICEFLOW_COMPUTE_ENV"
aws batch list-jobs --job-queue "$RICEFLOW_QUEUE" --job-status RUNNING
aws batch list-jobs --job-queue "$RICEFLOW_QUEUE" --job-status RUNNABLE
aws batch describe-jobs --jobs <recorded-job-ids>
aws ec2 describe-instances --filters Name=tag:Project,Values=RiceFlow
aws ec2 describe-volumes --filters Name=tag:Project,Values=RiceFlow
aws ec2 describe-snapshots --owner-ids self
aws ec2 describe-addresses
aws s3 ls "$RICEFLOW_S3/work/" --recursive --summarize
aws ecr describe-images --repository-name riceflow-demo
aws logs describe-log-groups --log-group-name-prefix /aws/batch/riceflow-demo
```

Recovery/cancellation commands below are prepared; obtain appropriate authorization before executing
against live scientific jobs/resources. Cancel queued jobs and terminate started jobs, then verify all
recorded jobs terminal before stopping the controller. After abrupt controller death, an external
operator must enumerate ALL active statuses (SUBMITTED/PENDING/RUNNABLE/STARTING/RUNNING), terminate
or recover them and inspect residual workers. No local finally block survives power loss.

```bash
aws batch cancel-job --job-id <queued-id> --reason 'authorized run cancellation'
aws batch terminate-job --job-id <started-id> --reason 'authorized run cancellation'
aws ec2 stop-instances --instance-ids <controller-id>
aws ec2 wait instance-stopped --instance-ids <controller-id>
# With separate teardown authorization, after exporting state/cache and preserving scientific outputs:
terraform -chdir=infra/terraform plan -destroy -out=destroy.tfplan
terraform -chdir=infra/terraform apply destroy.tfplan
```

The data bucket has `prevent_destroy`; teardown requires deliberately removing that guard only with
specific authorization, and a nonempty bucket is not force-deleted. Do not delete work objects during
the 30-day resume window. Work and controller backups expire at 30 days; results/inputs/reference have
no automatic expiration. ECR expires untagged images after seven days; remove old tagged releases only
when no needed work depends on them. Inspect persistent EBS, snapshots, IPs, logs, S3 and ECR after
compute shutdown. Budget alerts ($5/$10/$15) are delayed notifications, not hard caps.

Remaining cloud integration gates: first authorized deployment/plan review, ECR upload/digest lock,
S3 input staging/finalization integration, observed IAM behavior, queue deadline/cancellation,
controller stop, worker scale-to-zero, restore/resume, telemetry and cost ledger. Local Terraform
validation is not deployment validation. These remain explicit rather than simulated pass claims.
