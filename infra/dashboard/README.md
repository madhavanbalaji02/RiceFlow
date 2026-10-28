# Private static dashboard hosting

**Public dashboard: https://d35x4x7bn6ghj.cloudfront.net/**

Deployed and checked without authentication. [Deployment record](deployment.json) contains resource IDs, verification time and test totals, with account IDs and full ARNs omitted. The local private receipt holds the full identifiers.

This stack serves only the RiceFlow dashboard through the default CloudFront HTTPS domain. The S3 origin is private, with all four Block Public Access settings enabled, SSE-S3 encryption, and a bucket policy allowing only this distribution through signed Origin Access Control. GET/HEAD are the only viewer methods. There is no application server, pipeline execution, custom domain, logging destination, database, or live AWS monitoring.

## Pricing and enrollment

The template explicitly uses `AWS::PricingPlanManager::Subscription`, `PlanFamily: CloudFront`, `PlanTier: FREE`. The [CloudFront Free flat-rate plan](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html) has a $0 monthly subscription, 1 million requests and 100 GB monthly transfer allowances, and monthly S3 Standard storage credits for 5 GB across the payer account. This is distinct from the general AWS Free Tier account plan and temporary promotional credits. There are no CloudFront overage charges; sustained excessive usage can affect performance. Do not upgrade the plan automatically.

AWS requires a WAF ACL and distribution to exist before [API enrollment](https://docs.aws.amazon.com/PricingPlanManager/latest/UserGuide/getting-started-pricingplanmanager-api.html). The supported [CloudFormation subscription resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-pricingplanmanager-subscription.html) therefore follows those resources. Initial provisioning is blocked by default. The owner explicitly approved a $0.02 setup allowance: create a **disabled** distribution and empty mandatory WAF ACL, verify the actual subscription is **ACTIVE/FREE**, upload assets, then enable traffic. Unbundled WAF costs $5/month prorated hourly (about $0.007/hour) until enrollment; failed enrollment requests scoped rollback while the site remains disabled. No paid subscription approval API is called. No console-only step or unsupported pricing flag is used. The stack and PricingPlanManager endpoint use `us-east-1`; historical Ohio workflow resources are separate.

[S3 requests](https://aws.amazon.com/s3/pricing/) remain billable: PUT/LIST $0.005 per 1,000, GET/HEAD $0.0004 per 1,000 in US East. Storage credits do not cover these requests. Incoming uploads and S3-to-CloudFront transfer have no data-transfer charge. Object tagging is deliberately avoided because it carries a recurring fee; publisher ownership uses free object metadata. Supported resources receive Project=RiceFlow, Component=StaticDashboard, ManagedBy=RiceFlowDashboardPublisher tags. OAC/subscription identifiers are recorded because these resource APIs do not support tags.

Illustrative monthly estimate, excluding tax and unrelated resources:

| Item | Assumption | Estimate |
| --- | --- | ---: |
| CloudFront/WAF plan | Active Free subscription; ~2.4 GB delivered for 1,000 full visits | $0 |
| S3 Standard storage | ~2.4 MB dashboard; payer total remains below credited 5 GB | $0 after plan credit |
| Origin requests | Conservative 6,000 GETs; caching generally reduces this | $0.00240 |
| Upload requests | One full six-object upload | $0.00003 |
| Total example | 1,000 visits, one update/month | **$0.00243/month** |

Preflight found a standalone active paid-plan account, zero existing Free subscriptions and 1,061,631,175 bytes of S3 Standard objects before this dashboard. Read-only preflight/verification also make small request charges. Without the plan's storage credit, the dashboard alone would be about $0.000052/month at $0.023/GB-month. Future account storage growth or pricing changes require a new review; preflight refuses an exhausted allowance or unreviewed organization-wide credit sharing. This targets a $0 recurring hosting subscription, **not an entirely zero AWS bill**. Existing compute/storage/log charges are unrelated and remain untouched.

## Build and review

From the repository root, Python 3.11+ and Node 22+:

```bash
make -f dashboard/Makefile dashboard-test dashboard-publish
python3 -m http.server 8765 --bind 127.0.0.1 --directory dist/dashboard
# Open http://127.0.0.1:8765/
```

The stdlib builder exports existing certified reports without executing them. It preserves SUCCESS, INCOMPLETE and FAILED, scientific limitations, independent cohort/VCF tracks and historical AWS labels. Certification is artifact integrity, not a new biological validation. It rejects private paths, AWS account/credential fields, ARNs and altered certified artifacts. Inspect the snapshot and six-file manifest before publication:

```bash
python3 -m json.tool dist/dashboard-manifest.json
```

Only `index.html` and five fingerprinted assets (JS, logic module, CSS, SVG, JSON) are uploaded. Everything else, including tests, logs, archives, credentials, raw datasets, original HTML reports and deployment receipts, stays out of the origin. URLs are relative; JSON resolves relative to its module, so root and project-prefix previews work. Index uses revalidation; content-hashed assets cache for one year. MIME types and SHA-256 digests are verified after upload. Hash navigation needs no server rewrite.

Optional browser checks (development dependencies never enter the website):

```bash
npm ci --prefix dashboard/tests
npm exec --prefix dashboard/tests -- playwright install chromium
DASHBOARD_URL=http://127.0.0.1:8765/ node dashboard/tests/browser.test.mjs
```

The suite checks both desktop and mobile, run selection, sample search, variant decisions, comparisons, provenance, CSV/JSON downloads and local snapshot import, responsive navigation and absence of write requests. Screenshots/results stay in ignored `.tools/dashboard-qa/`. Dashboard CI runs these checks. Existing scientific jobs retain their commands and run on non-dashboard changes; workflow configuration-only edits can use the existing workflow's manual dispatch. Publishing the dashboard does not execute those jobs.

## Deploy or update

Use existing local AWS credentials, an AWS profile, or the ignored local `.env`; never commit credentials. Install the pinned SDK separately from scientific dependencies:

```bash
uv venv --python 3.11 .tools/dashboard-aws-venv
uv pip install --python .tools/dashboard-aws-venv/bin/python -r infra/dashboard/requirements.lock
.tools/dashboard-aws-venv/bin/python scripts/dashboard_aws.py preflight
# First deployment only, with the separately approved staging allowance:
.tools/dashboard-aws-venv/bin/python scripts/dashboard_aws.py deploy --allow-staged-enrollment
```

Updates reuse the same tagged stack and verify the active Free subscription before uploading:

```bash
make -f dashboard/Makefile dashboard-publish
.tools/dashboard-aws-venv/bin/python scripts/dashboard_aws.py deploy
.tools/dashboard-aws-venv/bin/python scripts/dashboard_aws.py verify
.tools/dashboard-aws-venv/bin/python scripts/dashboard_aws.py status
```

The uploader switches index last. Older fingerprinted static assets may remain for existing tabs; no unrelated files are copied. Future builds count account storage before deployment. No CloudFront invalidation is needed. `.tools/dashboard-deployment/hosting-state.json` is the mode-0600 receipt with account, stack ARN, resource ARNs, actual plan and verification results. Keep it for scoped teardown; do not publish it or `.env`. Deployment configuration and any errors can be inspected in CloudFormation for `riceflow-static-dashboard`, region `us-east-1`. If enrollment fails, inspect stack events and the disabled staging rollback; never enable a distribution on PAYG as a workaround.

## Teardown

Run only when you intend to remove this dashboard:

```bash
.tools/dashboard-aws-venv/bin/python scripts/dashboard_aws.py teardown --confirm-teardown riceflow-static-dashboard
```

This requires matching local receipt, ownership tags and the exact reviewed six-resource template. It refuses unexpected objects or template drift. It first disables the distribution and waits, then deletes only publisher-owned static objects and requests deletion of this stack. CloudFormation cancels the Free subscription before deleting its dependencies. Watch the stack reach DELETE_COMPLETE in the console; the command reports TEARDOWN_REQUESTED until that deletion finishes. **Do not cancel the plan while public traffic is enabled**: cancellation returns a distribution to pay-as-you-go. Other stacks, S3 buckets, workflows, budgets, IAM policies and historical science resources are outside this command's scope. If the receipt is lost or drift is detected, review this stack manually rather than weakening these safeguards.
