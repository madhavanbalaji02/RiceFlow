SHELL := /bin/bash
export PATH := $(CURDIR)/.venv/bin:$(CURDIR)/.tools:$(PATH)
export NXF_HOME := $(CURDIR)/.tools/nxf-home
export JAVA_CMD := $(shell command -v java)
.PHONY: setup test lint demo preflight real-demo report resume recovery workflow-test container cloud-validate
setup:
	bash scripts/setup.sh
test:
	PATH="$(PATH)" .venv/bin/python -m pytest -q
lint:
	.venv/bin/python -m ruff check src tests scripts
	.tools/terraform -chdir=infra/terraform fmt -check
workflow-test:
	PATH="$(PATH)" .venv/bin/python scripts/prepare-nf-test.py
	PATH="$(PATH)" .tools/nf-test test --verbose
demo:
	PATH="$(PATH)" .venv/bin/riceflow run --config config/demo.yaml
preflight:
	.venv/bin/python -m riceflow.preflight --out data/real
real-demo:
	PATH="$(PATH)" .venv/bin/riceflow run --config config/real.yaml
report:
	PATH="$(PATH)" .venv/bin/riceflow report --out "$(RUN)" --label "$(LABEL)"
resume:
	test -n "$(SESSION)"
	PATH="$(PATH)" .venv/bin/riceflow run --config $(or $(CONFIG),config/demo.yaml) --resume "$(SESSION)"
recovery:
	PATH="$(PATH)" .venv/bin/python scripts/recovery-demo.py
container:
	bash scripts/lock-container.sh
cloud-validate:
	.tools/terraform -chdir=infra/terraform init -backend=false -input=false
	.tools/terraform -chdir=infra/terraform validate
