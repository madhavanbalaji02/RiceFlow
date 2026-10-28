#!/usr/bin/env python3
"""Private S3 + OAC + an explicitly FREE CloudFront flat-rate subscription.

No pipeline execution. New-resource enrollment is guarded because AWS requires a
pre-existing disabled distribution and WAF ACL before activating the Free plan.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'infra/dashboard/template.json'
TAGS = {'Project': 'RiceFlow', 'Component': 'StaticDashboard',
        'ManagedBy': 'RiceFlowDashboardPublisher'}
REGION = 'us-east-1'


def private_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as handle:
        os.chmod(temporary, 0o600)
        json.dump(data, handle, indent=2, default=str)
        handle.write('\n')
    temporary.replace(path)


def session(env_file):
    import boto3
    from botocore.config import Config
    values = {}
    if env_file and Path(env_file).is_file():
        allowed = {'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
                   'AWS_DEFAULT_REGION', 'AWS_ACCOUNT_ID', 'AWS_PROFILE'}
        for line in Path(env_file).read_text().splitlines():
            key, sep, value = line.strip().removeprefix('export ').partition('=')
            if sep and key.strip() in allowed:
                parts = shlex.split(value, comments=True)
                if len(parts) > 1:
                    raise ValueError(f'Invalid whitespace in {key.strip()}')
                values[key.strip()] = parts[0] if parts else ''
    # Environment and existing credential chains take priority; never print credentials.
    credential_keys = {'aws_access_key_id': 'AWS_ACCESS_KEY_ID',
                       'aws_secret_access_key': 'AWS_SECRET_ACCESS_KEY',
                       'aws_session_token': 'AWS_SESSION_TOKEN'}
    kwargs = {name: os.environ.get(key) or values.get(key) for name, key in credential_keys.items()}
    kwargs = {name: value for name, value in kwargs.items() if value}
    if not kwargs and (os.environ.get('AWS_PROFILE') or values.get('AWS_PROFILE')):
        kwargs['profile_name'] = os.environ.get('AWS_PROFILE') or values['AWS_PROFILE']
    sdk = boto3.Session(region_name=REGION, **kwargs)
    config = Config(connect_timeout=5, read_timeout=30, retries={'mode': 'standard', 'max_attempts': 2})
    clients = {name: sdk.client(name, region_name=REGION, config=config)
               for name in ['sts', 's3', 'cloudfront', 'wafv2', 'cloudformation',
                            'freetier', 'pricing-plan-manager', 'organizations']}
    account = clients['sts'].get_caller_identity()['Account']
    expected = os.environ.get('AWS_ACCOUNT_ID') or values.get('AWS_ACCOUNT_ID')
    if expected and expected != account:
        raise ValueError('Authenticated account differs from AWS_ACCOUNT_ID')
    return clients, account


def check_template(template):
    resources = template['Resources']
    expected = {'AWS::S3::Bucket', 'AWS::S3::BucketPolicy', 'AWS::CloudFront::Distribution',
                'AWS::CloudFront::OriginAccessControl', 'AWS::WAFv2::WebACL',
                'AWS::PricingPlanManager::Subscription'}
    if {r['Type'] for r in resources.values()} != expected or len(resources) != 6:
        raise ValueError('Only the six required dashboard resources are allowed')
    plan = resources['DashboardFreeSubscription']['Properties']
    if plan['PlanFamily'] != 'CloudFront' or plan['PlanTier'] != 'FREE':
        raise ValueError('Only the FREE flat-rate plan is authorized')
    block = resources['DashboardBucket']['Properties']['PublicAccessBlockConfiguration']
    if set(block.values()) != {True}:
        raise ValueError('All S3 public-access blocks must remain enabled')
    distribution = resources['DashboardDistribution']['Properties']['DistributionConfig']
    if distribution['Enabled'] != {'Fn::If': ['ServeDashboard', True, False]}:
        raise ValueError('Distribution enablement must be gated')
    if distribution['DefaultCacheBehavior']['AllowedMethods'] != ['GET', 'HEAD']:
        raise ValueError('The dashboard must remain read-only')
    return template


def verify_free(subscription, outputs):
    data = subscription['subscription']
    if (data.get('planFamily') != 'CloudFront' or data.get('planTier') != 'FREE'
            or data.get('status') != 'ACTIVE' or data.get('scheduledChange')):
        raise ValueError('An active FREE subscription without pending changes is required')
    expected = {outputs['DistributionArn'], outputs['WebACLArn']}
    if set(data.get('resourceArns', [])) != expected:
        raise ValueError('Subscription resources do not match this dashboard')
    return data


def stack_info(clients, name):
    try:
        return clients['cloudformation'].describe_stacks(StackName=name)['Stacks'][0]
    except clients['cloudformation'].exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'ValidationError' and 'does not exist' in str(error):
            return None
        raise


def owned(stack):
    tags = {t['Key']: t['Value'] for t in stack.get('Tags', [])}
    if any(tags.get(k) != v for k, v in TAGS.items()):
        raise ValueError('Refusing to modify a stack without dashboard ownership tags')
    return {o['OutputKey']: o['OutputValue'] for o in stack.get('Outputs', [])}


def validate_live_stack(clients, stack, template):
    owned(stack)
    live = clients['cloudformation'].get_template(StackName=stack['StackId'], TemplateStage='Original')['TemplateBody']
    if isinstance(live, str):
        live = json.loads(live)
    check_template(live)
    if live['Resources'] != template['Resources']:
        raise ValueError('Live stack differs from the reviewed six resources; refusing replacement or deletion')


def rollback_staging(clients, stack_id, template):
    """Only a newly created, still-disabled stack can enter this rollback path."""
    for _ in range(120):
        stack = stack_info(clients, stack_id)
        if not stack:
            return
        validate_live_stack(clients, stack, template)
        parameters = {p['ParameterKey']: p['ParameterValue'] for p in stack['Parameters']}
        if parameters.get('SiteEnabled') != 'false':
            raise ValueError('Automatic staging rollback refuses an enabled site')
        if stack['StackStatus'].endswith('_IN_PROGRESS'):
            time.sleep(15)
            continue
        clients['cloudformation'].delete_stack(StackName=stack_id)
        print('Failed disabled staging stack: scoped deletion requested', flush=True)
        return
    raise TimeoutError('Staging rollback still pending; inspect this dashboard stack immediately')


def wait_stack(clients, name, deadline=1800):
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        stack = stack_info(clients, name)
        if stack is None:
            return None
        state = stack['StackStatus']
        print('Stack:', state, flush=True)
        if state in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
            return stack
        if state.endswith('FAILED') or 'ROLLBACK' in state:
            raise RuntimeError(f'Dashboard stack failed: {state}; inspect its events, do not enable traffic')
        time.sleep(15)
    raise TimeoutError('Dashboard stack deadline reached; inspect status before retrying')


def update_enabled(clients, stack, template, enabled):
    validate_live_stack(clients, stack, template)
    try:
        clients['cloudformation'].update_stack(
            StackName=stack['StackId'], TemplateBody=json.dumps(template),
            Parameters=[{'ParameterKey': 'SiteEnabled', 'ParameterValue': str(enabled).lower()}],
            Tags=[{'Key': k, 'Value': v} for k, v in TAGS.items()])
    except clients['cloudformation'].exceptions.ClientError as error:
        if 'No updates are to be performed' not in str(error):
            raise
    return wait_stack(clients, stack['StackId'])


def storage_inventory(clients, max_pages=100):
    total = 0
    pages = 0
    for bucket in clients['s3'].list_buckets()['Buckets']:
        versioned = clients['s3'].get_bucket_versioning(Bucket=bucket['Name']).get('Status')
        operation = 'list_object_versions' if versioned in ['Enabled', 'Suspended'] else 'list_objects_v2'
        for page in clients['s3'].get_paginator(operation).paginate(Bucket=bucket['Name']):
            pages += 1
            if pages > max_pages:
                raise ValueError('Storage inventory cap reached; allowance cannot be established')
            entries = page.get('Versions', []) if operation == 'list_object_versions' else page.get('Contents', [])
            total += sum(o['Size'] for o in entries if o.get('StorageClass', 'STANDARD') == 'STANDARD')
    return total


def preflight(clients, account, stack_name, manifest):
    try:
        clients['organizations'].describe_organization()
    except clients['organizations'].exceptions.AWSOrganizationsNotInUseException:
        pass
    else:
        raise ValueError('Shared payer storage credits require a separate organization-wide cost review')
    plan = clients['freetier'].get_account_plan_state()
    if plan['accountPlanType'] != 'PAID' or plan['accountPlanStatus'] != 'ACTIVE':
        raise ValueError('CloudFront flat-rate plans require an active paid AWS account plan')
    plans = [s for page in clients['pricing-plan-manager'].get_paginator('list_subscriptions').paginate()
             for s in page.get('subscriptionSummaries', [])]
    existing = stack_info(clients, stack_name)
    if existing:
        owned(existing)
    elif sum(s.get('planTier') == 'FREE' for s in plans) >= 3:
        raise ValueError('The account already has three Free plans; no resources created')
    total = storage_inventory(clients)
    if total + manifest['total_bytes'] > 5 * 1024**3:
        raise ValueError('Shared 5 GB storage allowance may be exceeded; stop before provisioning')
    clients['cloudformation'].describe_type(Type='RESOURCE', TypeName='AWS::PricingPlanManager::Subscription')
    template = check_template(json.loads(TEMPLATE.read_text()))
    clients['cloudformation'].validate_template(TemplateBody=json.dumps(template))
    return {'account_matches': True, 'account_plan': 'PAID/ACTIVE',
            'existing_stack': bool(existing), 'plan_family': 'CloudFront', 'requested_tier': 'FREE',
            'current_standard_storage_bytes': total, 'dashboard_bytes': manifest['total_bytes'],
            'monthly_storage_allowance_bytes': 5 * 1024**3,
            'monthly_cloudfront_plan_usd': 0, 'upload_s3_puts': len(manifest['assets']),
            'upload_request_estimate_usd': len(manifest['assets']) * .005 / 1000,
            'example_monthly_request_usd': 1000 * 6 * .0004 / 1000 + 6 * .005 / 1000,
            'request_assumptions': '1000 visits/month, at most 6 origin GETs/visit and one full upload; CDN caching usually reduces origin GETs.',
            'initial_enrollment_note': 'The API/CloudFormation must create a disabled distribution and mandatory WAF ACL before the actual FREE subscription can be read back. Unbundled WAF is $5/month prorated hourly until enrolled. No new resources are created without explicit enrollment acknowledgement.',
            'changes_performed': False}


def load_assets(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory.parent / (directory.name + '-manifest.json')).read_text())
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual != set(manifest['assets']) or len(actual) != 6:
        raise ValueError('Static deployment must contain exactly the six publisher assets')
    for name, value in manifest['assets'].items():
        path = directory / name
        if not path.resolve().is_relative_to(directory) or path.is_symlink():
            raise ValueError('Linked or out-of-root assets are forbidden')
        if hashlib.sha256(path.read_bytes()).hexdigest() != value['sha256']:
            raise ValueError('Static asset digest does not match the reviewed manifest')
    if any(p.is_symlink() for p in directory.rglob('*')):
        raise ValueError('Static deployment cannot contain links')
    return manifest


def current_free(clients, outputs):
    return verify_free(clients['pricing-plan-manager'].get_subscription(arn=outputs['SubscriptionArn']), outputs)


def upload(clients, account, outputs, manifest, directory):
    current_free(clients, outputs)
    bucket = outputs['BucketName']
    # Upload immutable assets first and switch index last; no invalidations or extra services.
    for name in sorted(manifest['assets'], key=lambda n: n == 'index.html'):
        item = manifest['assets'][name]
        response = clients['s3'].put_object(
            Bucket=bucket, Key=name, Body=(directory / name).read_bytes(),
            ContentType=item['content_type'], CacheControl=item['cache_control'],
            ChecksumSHA256=base64.b64encode(bytes.fromhex(item['sha256'])).decode(),
            ExpectedBucketOwner=account,
            Metadata={'riceflow-publisher': 'static-dashboard-v1'})
        if response.get('ChecksumSHA256') != base64.b64encode(bytes.fromhex(item['sha256'])).decode():
            raise ValueError('S3 did not confirm the supplied content checksum')
        print('Published:', name, flush=True)


def verify(clients, account, outputs, manifest):
    from botocore.httpsession import get_cert_path
    tls = ssl.create_default_context(cafile=os.environ.get('AWS_CA_BUNDLE') or get_cert_path(True))
    subscription = current_free(clients, outputs)
    distribution = clients['cloudfront'].get_distribution(Id=outputs['DistributionId'])['Distribution']
    config = distribution['DistributionConfig']
    if (distribution['Status'] != 'Deployed' or not config['Enabled']
            or config['DefaultRootObject'] != 'index.html'
            or not config['ViewerCertificate'].get('CloudFrontDefaultCertificate')
            or set(config['DefaultCacheBehavior']['AllowedMethods']['Items']) != {'GET', 'HEAD'}
            or config['Origins']['Items'][0]['OriginAccessControlId'] != outputs['OriginAccessControlId']
            or config['WebACLId'] != outputs['WebACLArn']):
        raise ValueError('Live distribution does not match the reviewed private, read-only HTTPS configuration')
    bucket = outputs['BucketName']
    block = clients['s3'].get_public_access_block(Bucket=bucket, ExpectedBucketOwner=account)
    if set(block['PublicAccessBlockConfiguration'].values()) != {True}:
        raise ValueError('S3 public access block is not fully enabled')
    policy = json.loads(clients['s3'].get_bucket_policy(Bucket=bucket, ExpectedBucketOwner=account)['Policy'])
    statement = policy['Statement']
    if len(statement) != 1 or statement[0]['Principal'] != {'Service': 'cloudfront.amazonaws.com'}:
        raise ValueError('Unexpected S3 origin permissions')
    if statement[0]['Condition']['StringEquals']['AWS:SourceArn'] != outputs['DistributionArn']:
        raise ValueError('S3 origin is not restricted to this distribution')
    origin_url = f'https://{bucket}.s3.{REGION}.amazonaws.com/index.html'
    try:
        urllib.request.urlopen(origin_url, timeout=30, context=tls)
        raise ValueError('Anonymous S3 origin access unexpectedly succeeded')
    except urllib.error.HTTPError as error:
        if error.code != 403:
            raise
    url = 'https://' + outputs['DomainName'] + '/'
    with urllib.request.urlopen(url, timeout=30, context=tls) as response:
        if hashlib.sha256(response.read()).hexdigest() != manifest['assets']['index.html']['sha256']:
            raise ValueError('Public root does not serve the reviewed index.html')
    checked = []
    for name, item in manifest['assets'].items():
        with urllib.request.urlopen(url + name, timeout=30, context=tls) as response:
            if hashlib.sha256(response.read()).hexdigest() != item['sha256']:
                raise ValueError(f'Public asset mismatch: {name}')
            if response.headers.get_content_type() != item['content_type'].split(';')[0]:
                raise ValueError(f'Public MIME mismatch: {name}')
            if response.headers.get('Cache-Control') != item['cache_control']:
                raise ValueError(f'Public cache header mismatch: {name}')
            checked.append(name)
    return {'status': 'DEPLOYED_AND_VERIFIED', 'url': url, 'plan': subscription['planTier'],
            'subscription_status': subscription['status'], 'private_origin_anonymous_status': 403,
            'public_assets_verified': checked, 'verified_utc': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'deploy', 'status', 'verify', 'teardown'])
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--stack', default='riceflow-static-dashboard')
    parser.add_argument('--directory', type=Path, default=ROOT / 'dist/dashboard')
    parser.add_argument('--state', type=Path, default=ROOT / '.tools/dashboard-deployment/hosting-state.json')
    parser.add_argument('--allow-staged-enrollment', action='store_true',
                        help='Explicit additional consent for disabled resource/WAF staging before FREE activation')
    parser.add_argument('--confirm-teardown', help='Must match the stack name; deletes only this tagged dashboard stack')
    args = parser.parse_args()
    clients, account = session(args.env_file)
    template = check_template(json.loads(TEMPLATE.read_text()))
    manifest = load_assets(args.directory) if args.action != 'teardown' else None
    if args.action == 'preflight':
        result = preflight(clients, account, args.stack, manifest)
        private_json(args.state.parent / 'hosting-preflight.json', result)
        print(json.dumps(result, indent=2))
        return
    stack = stack_info(clients, args.stack)
    if args.action == 'deploy':
        report = preflight(clients, account, args.stack, manifest)
        private_json(args.state.parent / 'hosting-preflight.json', report)
        if stack is None:
            if not args.allow_staged_enrollment:
                raise ValueError(report['initial_enrollment_note'] + ' Creation blocked by the user cost constraint.')
            response = clients['cloudformation'].create_stack(
                StackName=args.stack, TemplateBody=json.dumps(template),
                Parameters=[{'ParameterKey': 'SiteEnabled', 'ParameterValue': 'false'}],
                Tags=[{'Key': k, 'Value': v} for k, v in TAGS.items()],
                TimeoutInMinutes=30, OnFailure='ROLLBACK')
            private_json(args.state, {'account_id': account, 'stack_id': response['StackId'], 'status': 'CREATING_DISABLED'})
            try:
                stack = wait_stack(clients, response['StackId'])
                current_free(clients, owned(stack))
            except Exception:
                rollback_staging(clients, response['StackId'], template)
                raise
        outputs = owned(stack)
        validate_live_stack(clients, stack, template)
        current_free(clients, outputs)
        upload(clients, account, outputs, manifest, args.directory.resolve())
        stack = update_enabled(clients, stack, template, True)
        outputs = owned(stack)
        result = verify(clients, account, outputs, manifest)
    elif args.action in ['status', 'verify']:
        if not stack:
            raise ValueError('No dashboard stack exists; deployment has not occurred')
        outputs = owned(stack)
        current_free(clients, outputs)
        result = verify(clients, account, outputs, manifest) if args.action == 'verify' else {'status': stack['StackStatus'], 'url': 'https://' + outputs['DomainName'] + '/', 'plan': 'FREE'}
    else:
        if args.confirm_teardown != args.stack or not stack:
            raise ValueError('Teardown requires the exact existing stack name and confirmation')
        outputs = owned(stack)
        validate_live_stack(clients, stack, template)
        saved = json.loads(args.state.read_text())
        if saved.get('account_id') != account or saved.get('stack_id') != stack['StackId']:
            raise ValueError('Teardown requires the matching local deployment receipt')
        current_free(clients, outputs)
        bucket = outputs['BucketName']
        keys = [o['Key'] for page in clients['s3'].get_paginator('list_objects_v2').paginate(Bucket=bucket) for o in page.get('Contents', [])]
        for key in keys:
            metadata = clients['s3'].head_object(Bucket=bucket, Key=key, ExpectedBucketOwner=account)['Metadata']
            allowed = key == 'index.html' or re.fullmatch(r'assets/(?:data|logic|app|styles|icon)\.[0-9a-f]{16}\.(?:json|mjs|js|css|svg)', key)
            if not allowed or metadata.get('riceflow-publisher') != 'static-dashboard-v1':
                raise ValueError('Bucket contains an object not owned by this publisher; teardown refused')
        stack = update_enabled(clients, stack, template, False)
        # The subscription is canceled by CloudFormation only after traffic is disabled.
        for offset in range(0, len(keys), 1000):
            clients['s3'].delete_objects(Bucket=bucket, Delete={'Objects': [{'Key': k} for k in keys[offset:offset + 1000]]})
        clients['cloudformation'].delete_stack(StackName=stack['StackId'])
        result = {'status': 'TEARDOWN_REQUESTED', 'stack_id': stack['StackId'],
                  'note': 'Monitor delete-stack completion; only this tagged stack and its publisher-owned static objects were selected.'}
    if args.action != 'teardown':
        result.update({'account_id': account, 'stack_id': stack['StackId'], 'resources': outputs})
    private_json(args.state, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
