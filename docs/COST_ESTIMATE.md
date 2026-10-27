# AWS cost planning — no cloud run authorized

Target: at most USD 15/month before taxes and promotional credits. This is a planning target, not
a hard spending cap. No AWS resources have been provisioned, no cloud runtime has been measured,
and no actual billing usage has been obtained. Project usage cannot be inferred as zero from this
local workspace. Remaining allowance is UNKNOWN until account billing and retained resources are checked.
Cloud submission is blocked until a specific estimate and observed usage are reviewed by the user.

Initial aggregate planning ceilings: 20 worker instance-hours and 20 controller-hours/month, including
retries and idle time. They are not per-job allowances or a guarantee of a USD 15 bill. Lower them if
the full conservative estimate does not fit. The profile uses min vCPUs 0, max vCPUs 2 (configurable up
to 4), one c6i.large CPU worker allowlist, t3.small controller, queue/concurrency 1, 15-minute tasks,
no retries and a 30-minute run deadline. Batch BEST_FIT_PROGRESSIVE can exceed maxvCPUs by one instance;
max vCPUs is not a dollar cap. Include that excess capacity in the estimate.

Before any authorized deployment, query current official us-east-1 rates and fill every row below.
Use current on-demand rates conservatively, with no assumed free tier/credits or Spot savings.

| Item | Explicit usage assumption | Cost formula / current estimate |
|---|---|---|
| Worker compute | ≤20 total c6i.large instance-hours incl. idle/retries/excess instances | hours × current EC2 rate; rate NOT YET VERIFIED |
| Controller compute | ≤20 t3.small hours, unlimited CPU credits disabled/reviewed | hours × rate + any CPU-credit charge; NOT YET VERIFIED |
| Public IPv4 | All running public workers + controller, no reserved IPs | address-hours × current VPC IPv4 rate; NOT YET VERIFIED |
| Controller EBS | 16 GiB gp3 retained up to 730 h/month | 16 × gp3 GiB-month rate; retained when stopped |
| Worker EBS | 30 GiB gp3 per worker for aggregate lifetime | 30 × hours/730 × gp3 rate |
| S3 | Start assumption ≤2 GiB incl. work and metadata, ≤10k PUT/LIST and 100k GET | storage + requests + transfer; adjust to observed object bytes |
| S3 transfers | Same-region Batch/S3; local public source input downloads; any external egress separately counted | verify transfer directions and tier; do not assume all traffic free |
| ECR | One measured image, retain necessary release tags only | actual image GiB × rate + any scanning/transfer charges |
| CloudWatch | ≤0.1 GiB ingest, 7-day retention | ingest + retained byte-months + queried bytes |
| Networking | Public subnet/IGW, no NAT/LB/paid interface endpoints | IPv4 above; verify transfer charges |
| Other retained costs | No snapshots or reserved IPs planned | inspect and add any EBS/snapshots/IPs from actual account |
| Budget service | Three actual-spend notifications at $5/$10/$15 | verify current notification/service pricing |

Official pages to recheck before authorization:
- https://aws.amazon.com/ec2/pricing/on-demand/
- https://aws.amazon.com/ebs/pricing/
- https://aws.amazon.com/vpc/pricing/
- https://aws.amazon.com/s3/pricing/
- https://aws.amazon.com/ecr/pricing/
- https://aws.amazon.com/cloudwatch/pricing/
- https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/

`conservative_run + observed_month + retained_month <= 15` is the minimum planning check; if usage
cannot be established confidently, stop submission and ask for a specific revised cost approval.
No blank/TBD line may be treated as zero. The controller authorization file requires numeric observed
usage, retained costs, planned usage and a price-verification timestamp within 24 hours.

| Cloud run ledger | Actual status |
|---|---|
| Authorized runs | None |
| Measured worker/controller hours | Not measured |
| Actual project-attributed billed cost | Unknown; requires account inspection |
| Remaining estimated monthly allowance | Unknown; submission blocked |

After each cloud run record instance launch/stop timestamps, instance type, aggregate worker/controller
hours, queue waiting, retries, idle time, disks, object/image sizes, log bytes and actual billing once
available. Enable/activate the Project allocation tag before using the filtered budget. Cost allocation
and billing are delayed. AWS Budgets alerts at $5/$10/$15 are notifications, not enforcement or immediate
shutdown. Receive the email address from the user before deployment; Terraform has no default recipient.
