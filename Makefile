NAMESPACE ?= kubeaiops
RELEASE ?= capacity-api
KIND_CLUSTER ?= kubeaiops
KUBE_CONTEXT ?= kind-kubeaiops
CHART ?= helm/capacity-api
IMAGE_TAG ?= dev
BASE_URL ?= http://127.0.0.1:8001
CAPACITY_API_URL ?= http://127.0.0.1:8000
TEST_PYTHON ?= $(CURDIR)/.member3-venv/bin/python
RESULTS_DIR ?= docs/evidence/member-3/load-tests
RECOVERY_RESULTS_DIR ?= docs/evidence/member-3/recovery
DATA_DIR ?= ml/capacity/data
RAW_DIR ?= $(DATA_DIR)/raw
PROCESSED_DIR ?= $(DATA_DIR)/processed
DATASET_VERSION ?= capacity-observations-v1
COLLECTION_DATE ?= 2026-07-25
SOURCE_COMMIT ?= $(shell git rev-parse --verify HEAD)
PROMETHEUS_URL ?= http://127.0.0.1:9090
EXTRACT_SCENARIO ?= normal
EXTRACT_START ?=
EXTRACT_END ?=
EXTRACT_STEP ?= 30s
RAW_EXPORT_DIR ?= $(RAW_DIR)/prometheus

.PHONY: setup-test-env test helm-lint helm-template images kind-load deploy-local verify-local k6-smoke load-normal load-progressive load-spike load-sustained test-recovery data-generate data-build data-pipeline data-validate extract-prometheus

setup-test-env:
	python3 -m venv $(CURDIR)/.member3-venv
	$(TEST_PYTHON) -m pip install --disable-pip-version-check -r services/capacity-api/requirements-dev.txt -r services/demo-workload/requirements-dev.txt

test:
	cd services/capacity-api && $(TEST_PYTHON) -m pytest -q
	cd services/demo-workload && $(TEST_PYTHON) -m pytest -q
	cd ml/capacity && PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) -m pytest -q

helm-lint:
	helm lint $(CHART)
	helm lint $(CHART) --values $(CHART)/values-local.yaml

helm-template:
	helm template $(RELEASE) $(CHART) --namespace $(NAMESPACE) --values $(CHART)/values-local.yaml > /tmp/capacity-api-rendered.yaml

images:
	docker build --build-arg APP_VERSION=0.1.0 --tag kubeaiops/capacity-api:$(IMAGE_TAG) services/capacity-api
	docker build --build-arg APP_VERSION=0.1.0 --tag kubeaiops/demo-workload:$(IMAGE_TAG) services/demo-workload

kind-load: images
	kind load docker-image kubeaiops/capacity-api:$(IMAGE_TAG) --name $(KIND_CLUSTER)
	kind load docker-image kubeaiops/demo-workload:$(IMAGE_TAG) --name $(KIND_CLUSTER)

deploy-local:
	helm upgrade --install $(RELEASE) $(CHART) --namespace $(NAMESPACE) --create-namespace --values $(CHART)/values-local.yaml --wait --timeout 3m

verify-local:
	kubectl -n $(NAMESPACE) get deployments,services,hpa
	kubectl -n $(NAMESPACE) wait --for=condition=Available deployment/capacity-api --timeout=120s
	kubectl -n $(NAMESPACE) wait --for=condition=Available deployment/demo-workload --timeout=120s

k6-smoke:
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) k6 run --summary-export=docs/evidence/member-3/k6-smoke-summary.json load-tests/capacity/smoke/k6-smoke.js

load-normal:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/normal-report.json k6 run --summary-export=$(RESULTS_DIR)/normal-summary.json load-tests/capacity/normal/k6-normal.js

load-progressive:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/progressive-report.json k6 run --summary-export=$(RESULTS_DIR)/progressive-summary.json load-tests/capacity/progressive/k6-progressive.js

load-spike:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/spike-report.json k6 run --summary-export=$(RESULTS_DIR)/spike-summary.json load-tests/capacity/spike/k6-spike.js

load-sustained:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/sustained-report.json k6 run --summary-export=$(RESULTS_DIR)/sustained-summary.json load-tests/capacity/sustained/k6-sustained.js

test-recovery:
	mkdir -p $(RECOVERY_RESULTS_DIR)
	NAMESPACE=$(NAMESPACE) RELEASE=$(RELEASE) KUBE_CONTEXT=$(KUBE_CONTEXT) RESULTS_DIR=$(RECOVERY_RESULTS_DIR) ALLOW_POD_DELETE=true bash scripts/capacity/run-recovery-test.sh

data-generate:
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/generate_synthetic_data.py --output-dir $(RAW_DIR) --source-commit $(SOURCE_COMMIT)

data-build:
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/build_dataset.py --raw-dir $(RAW_DIR) --processed-output $(PROCESSED_DIR)/$(DATASET_VERSION).csv --validation-report $(PROCESSED_DIR)/validation-report-v1.json --version-record $(PROCESSED_DIR)/dataset-v1.json --dataset-version $(DATASET_VERSION) --collection-date $(COLLECTION_DATE) --source-commit $(SOURCE_COMMIT)

data-pipeline: data-generate data-build

data-validate:
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/validate_dataset.py --dataset $(PROCESSED_DIR)/$(DATASET_VERSION).csv

extract-prometheus:
	test -n "$(EXTRACT_START)" && test -n "$(EXTRACT_END)"
	mkdir -p $(RAW_EXPORT_DIR)
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/extract_prometheus_metrics.py --prometheus-url $(PROMETHEUS_URL) --queries ml/capacity/config/prometheus-queries.json --start $(EXTRACT_START) --end $(EXTRACT_END) --step $(EXTRACT_STEP) --scenario $(EXTRACT_SCENARIO) --output $(RAW_EXPORT_DIR)/$(EXTRACT_SCENARIO).csv --config-output $(RAW_EXPORT_DIR)/$(EXTRACT_SCENARIO)-collection.json
