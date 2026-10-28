# AWS cost planning — refreshed 2026-10-27

## Authorized account follow-up — 2026-10-27

The user authorized the Ohio (`us-east-2`) demonstration, supplied the budget recipient and confirmed
prior account charges were unrelated to RiceFlow. Up to $5 additional was approved. Initial Project
cost attribution was inactive and the tag-filtered zero was not treated as proof of zero historical
spend. The tag is now active. Before deployment, no tagged RiceFlow resources/instances/volumes or
Batch environments were found in Ohio; this was a regional inventory, not a global historical audit.

The reviewed 31-create Terraform plan was applied. Verified inputs and source-matched immutable images
were uploaded, and the real cloud workflow passed both tracks. The $15 budget excludes taxes, credits
and refunds; the $5/$10/$15 actual-cost notifications were verified live. See
`reports/aws-demo-20261027-summary.json` for current shutdown and usage evidence. Raw billing responses,
deployment variables and saved plans remain ignored under `.tools/aws-session/` and the local cloud
report directory; credentials are not published.

The current official Ohio EC2 feed confirms the baseline worker/controller rates below. The official
Pricing API confirms Ohio gp3 at $0.08/GB-month, and the cached official multi-region S3 feed confirms
Ohio storage/request rates. The earlier $4.56 scenario plus a reserve for three Cost Explorer queries
at $0.01 each gives **$4.59**, below the approved $5 scenario. This is not actual billed cost or a cap.
The USD 15/month project target remains unchanged. The baseline below is preserved as the earlier
credential-free audit snapshot rather than rewritten as if deployment had happened then.

## Earlier credential-free audit baseline

The target remains USD 15/month before taxes and promotional credits. It is a planning target, not a
hard cap. No AWS provisioning, uploads or jobs have been performed. Account billing and retained
resources were not queried, so actual project spend and remaining monthly allowance are UNKNOWN.
A rate estimate does not authorize a cloud run. Fresh account usage, a specific approved estimate,
and a user-provided budget email are mandatory before submission.

Rates were checked against current official AWS sources on 2026-10-27. The public us-east-1 Linux
shared-tenancy on-demand feed (published 2026-10-23) gives c6i.large $0.085/hour and t3.small
$0.0208/hour. Exact rate codes, publication date, source URL and checksum are preserved in
[EC2 price evidence](../reports/audit-20261027/ec2-price-source.json). The current S3 Standard feed
(published 2026-10-15) gives $0.023/GB-month, $0.005/1,000 PUT/COPY/POST/LIST, and
$0.0004/1,000 GET. Its raw official feed and request metadata are preserved in the audit directory.
These are public pricing downloads, not authenticated AWS account operations.

The following is an explicit monthly usage scenario, not a prediction based on the small local run.
Retain the initial ceilings of 20 aggregate worker instance-hours and 20 controller-hours, including
queue waiting, retries, idle time and every simultaneous worker. Hours are not per-job allowances.
Use a 730-hour storage month, standard CPU credit mode, no credits/free-tier deductions, standard
gp3 baseline performance, no custom metrics/dashboards, no enhanced Inspector scanning and no NAT/LB.
Lower usage ceilings if a fresh conservative estimate does not fit the actual remaining allowance.

| Item | Official unit rate and explicit assumption | Monthly scenario USD |
|---|---|---:|
| CPU worker | 20 total c6i.large instance-hours × $0.085 | 1.7000 |
| Controller | 20 total t3.small hours × $0.0208; standard credits, no surplus-credit charge | 0.4160 |
| Public IPv4 | 40 aggregate address-hours × $0.005; no reserved/idle Elastic IPs planned | 0.2000 |
| Controller disk retained while stopped | 16 GB gp3 × $0.08 for the whole month | 1.2800 |
| Worker disks | 30 GB gp3 × $0.08 × 20/730 aggregate instance-hours | 0.0658 |
| S3 input/reference/work/results/cache | 2 GB-month total × $0.023 | 0.0460 |
| S3 writes/listing | 10,000 PUT/COPY/POST/LIST × $0.005/1,000 | 0.0500 |
| S3 reads | 100,000 GET × $0.0004/1,000 | 0.0400 |
| ECR retained images | Reserve 2 GB-month × $0.10; basic scanning; exact compressed registry size unmeasured | 0.2000 |
| CloudWatch Logs ingestion | 0.1 GB × $0.50, without free-tier deduction | 0.0500 |
| CloudWatch retained logs | Conservative 0.1 GB-month × $0.03 despite seven-day retention | 0.0030 |
| External/cross-region transfer reserve | 1 GB × $0.09; verify actual transfer direction/tier before a run | 0.0900 |
| Direct same-region S3/ECR ↔ EC2 transfer | Assumed direct same-region path; service request/storage charges above | 0.0000 |
| Batch service; budget monitoring/alerts | No additional Batch service fee; notification-only budgets are free | 0.0000 |
| NAT/LB/paid interface endpoints/database | None in the existing default configuration | 0.0000 |
| Snapshots, extra EBS, reserved IPs | None planned; actual retained account inventory remains uninspected | 0.0000 planned |
| Subtotal | Rounded line items; unrounded subtotal ≈ $4.1408 | 4.1408 |
| Planning contingency | 10% of subtotal; does not enforce a limit | 0.4141 |
| Scenario estimate | Rounded conservatively upward, before taxes/credits | **4.56** |

The local amd64 image inspected during the audit is 362,324,038 logical bytes. That is not a measured
ECR compressed-storage bill; 2 GB-month is deliberately reserved above for images and transient retained
layers. If more images/work objects accumulate, recalculate storage. The 2 GB S3 assumption is also
not an enforced quota; measure work/cache/output bytes before authorizing a cloud run.

Official sources supporting the rates and billing semantics:

- [EC2 on-demand and transfer](https://aws.amazon.com/ec2/pricing/on-demand/) and the public regional feed linked in the EC2 evidence JSON.
- [EBS gp3](https://aws.amazon.com/ebs/volume-types/) and [EBS billing](https://aws.amazon.com/ebs/pricing/): provisioned GB remains billable until released.
- [Public IPv4](https://aws.amazon.com/vpc/pricing/): $0.005/address-hour, including idle allocated addresses.
- [S3 storage/requests](https://aws.amazon.com/s3/pricing/) and its official price-feed artifact.
- [ECR](https://aws.amazon.com/ecr/pricing/): $0.10/GB-month and direction-dependent transfer charges; same-region EC2 pulls have no transfer-out charge.
- [CloudWatch](https://aws.amazon.com/cloudwatch/pricing/): standard log ingestion $0.50/GB and archive $0.03/GB-month; log querying/enhanced features are outside this assumed usage.
- [AWS Batch](https://aws.amazon.com/batch/pricing/) and [Budgets](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/): service/monitoring fees above; action-enabled budgets and emailed budget reports are not configured.

Existing controls remain CPU-only, min vCPUs zero, max vCPUs 2 (configurable 2–4), c6i.large allowlist,
queue concurrency one, no automatic task retries, 15-minute task bounds and a 30-minute controller
run deadline including queue wait. BEST_FIT_PROGRESSIVE may exceed max vCPUs by one instance.
Maximum vCPUs and the planning hour ceilings are not dollar caps. Reconcile all actual instances,
queue stalls, idle periods and retries rather than counting only successful task seconds.

Terraform retains the $5/$10/$15 actual-cost notification thresholds without an invented recipient.
The user must supply the email and activate the Project cost-allocation tag before deployment. Billing,
tag attribution and alerts can be delayed. Alerts are notifications, not enforcement or an immediate
shutdown mechanism. No new infrastructure was added in this audit.

| Cloud usage ledger | Actual state |
|---|---|
| Authorized cloud demonstrations | None |
| Measured cloud instance-hours | Unmeasured |
| Project-attributed billed cost / retained account resources | Unknown; not queried |
| Estimated remaining actual monthly allowance | **Unknown; cloud submission remains blocked** |

Before each authorized run require `conservative_run + observed_month + retained_month <= 15`, with
reliable usage evidence; otherwise stop submission and obtain specific revised approval. Do not treat
the difference between $15 and this hypothetical scenario as the actual remaining allowance.
After a run record launched/stopped instances, aggregate hours, disks/snapshots/IPs, S3/ECR bytes,
logs, requests and billing once available. Stop the controller only after jobs finish or are explicitly
cancelled, preserve Nextflow history/cache and the 30-day work window, and verify workers reach zero.
EBS, snapshots, reserved IPs, S3, ECR and logs can continue billing after compute stops.


### Executed demonstration cost boundary

Both failed attempts stopped before job submission and retained the same controller disk. The third
attempt completed three jobs on one c6i.large worker. Compute shutdown and the measured usage ledger
are recorded in `reports/aws-demo-20261027-summary.json`; actual invoiced cost is delayed and is not
claimed as the rate-based estimate. ECR retains two immutable versions with shared layers. The full
source/input uploads used cached local data; no full B001 VCF was downloaded.

The controller's retained 16 GB gp3 disk alone costs $1.28 per full month at the verified rate. S3,
ECR and logs add continuing storage charges until authorized cleanup. Scientific inputs/results have
no automatic expiration; work and controller backups retain the 30-day resume window. The existing
20 aggregate worker-hour and controller-hour monthly ceilings and USD 15 target remain in effect.
The explicitly approved additional allowance is USD 5. Alerts remain delayed notifications; no hard
dollar cap is claimed. Reconcile current billed usage and retained bytes before any subsequent run.


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

Cost Explorer query pricing: [official AWS pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/). Three primary-view GetCostAndUsage requests are reserved at $0.01 each.
