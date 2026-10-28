#!/bin/bash
# Authorized EC2-only bootstrap. Credentials come from the instance profile.
set -euo pipefail
: "${AWS_DEFAULT_REGION:?Set the reviewed deployment region}"
: "${RICEFLOW_PACKAGE_URI:?Set the reviewed S3 package URI}"
: "${RICEFLOW_PACKAGE_SHA256:?Set its expected SHA256}"
cd /opt/riceflow-controller
if [ ! -f project.tar.gz ]; then
    aws s3 cp "$RICEFLOW_PACKAGE_URI" project.tar.gz --only-show-errors
fi
printf '%s  project.tar.gz\n' "$RICEFLOW_PACKAGE_SHA256" | sha256sum -c -
mkdir -p project
tar -xzf project.tar.gz -C project
cd project
dnf -y install python3.11 python3.11-pip java-17-amazon-corretto-headless git
python3.11 -m venv .venv
.venv/bin/pip install --no-cache-dir -r requirements.lock
.venv/bin/pip install --no-cache-dir 'setuptools==80.9.0' 'wheel==0.45.1'
.venv/bin/pip install --no-deps --no-build-isolation -e .
export PATH="$PWD/.venv/bin:$PWD/.tools:$PATH"
export NXF_HOME="$PWD/.tools/nxf-home"
export NXF_OPTS='-Xms128m -Xmx768m'
export NXF_OFFLINE=true
export PYTHONUNBUFFERED=1
nextflow -version
python scripts/cloud-controller.py --authorization cloud-authorization.json --deadline 900 \
    riceflow run --profile aws --config config/aws-demo.yaml --out "${RICEFLOW_OUTDIR:-reports/aws-real}" --deadline 900
