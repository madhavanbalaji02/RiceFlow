#!/usr/bin/env bash
set -euo pipefail
mkdir -p .tools
if [ ! -x .venv/bin/python ]; then uv venv --python 3.11.14 .venv; fi
uv pip install --python .venv/bin/python -r requirements.lock pytest==8.4.2 ruff==0.14.2 setuptools==80.9.0
uv pip install --python .venv/bin/python --no-build-isolation --no-deps -e .
curl -fL --retry 2 --max-time 120 https://github.com/nextflow-io/nextflow/releases/download/v25.10.2/nextflow-25.10.2-dist -o .tools/nextflow
chmod +x .tools/nextflow
case "$(uname -s)-$(uname -m)" in
 Darwin-arm64) artifact=mac_arm64; tf_platform=darwin_arm64 ;;
 Linux-x86_64) artifact=linux_x86_64; tf_platform=linux_amd64 ;;
 *) echo 'Use the linux/amd64 Docker profile for this platform'; exit 1 ;;
esac
curl -fL --retry 2 --max-time 120 "https://s3.amazonaws.com/plink2-assets/alpha6/plink2_${artifact}_20250609.zip" -o .tools/plink.zip
unzip -o .tools/plink.zip -d .tools
curl -fL --retry 2 --max-time 120 https://github.com/askimed/nf-test/releases/download/v0.9.3/nf-test-0.9.3.tar.gz -o .tools/nf-test.tar.gz
tar -xzf .tools/nf-test.tar.gz -C .tools
# Native convenience adapters call compiled BCFtools/SAMtools bundled with pinned pysam.
cp scripts/bcftools-pysam .tools/bcftools
cp scripts/samtools-pysam .tools/samtools
chmod +x .tools/bcftools .tools/samtools
.venv/bin/python scripts/fixtures.py
.venv/bin/python scripts/prepare-nf-test.py

curl -fL --retry 2 --max-time 120 "https://releases.hashicorp.com/terraform/1.13.4/terraform_1.13.4_${tf_platform}.zip" -o .tools/terraform.zip
unzip -o .tools/terraform.zip -d .tools
