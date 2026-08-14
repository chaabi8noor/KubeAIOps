NAMESPACE ?= kubeaiops
RELEASE ?= capacity-api
KIND_CLUSTER ?= kubeaiops
KUBE_CONTEXT ?= kind-kubeaiops
CHART ?= helm/capacity-api
IMAGE_TAG ?= dev
BASE_URL ?= http://127.0.0.1:8001
CAPACITY_API_URL ?= http://127.0.0.1:8000
K6_RUNNER_PATH ?= scripts/capacity/run-k6.sh
TEST_PYTHON ?= $(CURDIR)/.member3-venv/bin/python
RESULTS_DIR ?= docs/evidence/member-3/load-tests
RECOVERY_RESULTS_DIR ?= docs/evidence/member-3/recovery
DATA_DIR ?= ml/capacity/data
RAW_DIR ?= $(DATA_DIR)/raw
PROCESSED_DIR ?= $(DATA_DIR)/processed
DATASET_VERSION ?= capacity-observations-v1
FEATURE_VERSION ?= features-v1
FEATURES_DIR ?= $(DATA_DIR)/features
FEATURE_CONFIG ?= ml/capacity/config/features.yaml
FEATURE_DATASET ?= $(FEATURES_DIR)/capacity-features-v1.csv
FEATURE_METADATA ?= $(FEATURES_DIR)/features-v1-metadata.json
BASELINE_CONFIG ?= ml/capacity/config/baseline.yaml
REPLICA_POLICY_CONFIG ?= ml/capacity/config/replica-policy.yaml
BASELINE_EVALUATION_DIR ?= ml/capacity/evaluation/baseline-v1
MODEL_CONFIG ?= ml/capacity/config/model.yaml
MODEL_ARTIFACT_DIR ?= ml/capacity/artifacts/primary-v1
PRIMARY_EVALUATION_DIR ?= ml/capacity/evaluation/primary-v1
MODEL_PACKAGE_DIR ?= services/capacity-api/models/primary-v1
COLLECTION_DATE ?= 2026-07-25
SOURCE_COMMIT ?= $(shell git rev-parse --verify HEAD)
PROMETHEUS_URL ?= http://127.0.0.1:9090
EXTRACT_SCENARIO ?= normal
EXTRACT_START ?=
EXTRACT_END ?=
EXTRACT_STEP ?= 30s
RAW_EXPORT_DIR ?= $(RAW_DIR)/prometheus

.PHONY: setup-test-env test helm-lint helm-template images kind-load deploy-local verify-local k6-smoke load-normal load-progressive load-spike load-sustained capacity-validation test-recovery test-api-resilience validation-evidence data-generate data-build data-pipeline data-validate extract-prometheus feature-build baseline-evaluate baseline-validation model-train model-validate package-model config-validate

setup-test-env:
	python3 -m venv $(CURDIR)/.member3-venv
	$(TEST_PYTHON) -m pip install --disable-pip-version-check -r services/capacity-api/requirements-dev.txt -r services/demo-workload/requirements-dev.txt -r ml/capacity/requirements.txt

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
	docker build --build-arg APP_VERSION=0.2.0 --tag kubeaiops/capacity-api:$(IMAGE_TAG) services/capacity-api
	docker build --build-arg APP_VERSION=0.2.0 --tag kubeaiops/demo-workload:$(IMAGE_TAG) services/demo-workload

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
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) bash $(K6_RUNNER_PATH) run --summary-export=docs/evidence/member-3/k6-smoke-summary.json load-tests/capacity/smoke/k6-smoke.js

load-normal:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/normal-report.json bash $(K6_RUNNER_PATH) run --summary-export=$(RESULTS_DIR)/normal-summary.json load-tests/capacity/normal/k6-normal.js

load-progressive:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/progressive-report.json bash $(K6_RUNNER_PATH) run --summary-export=$(RESULTS_DIR)/progressive-summary.json load-tests/capacity/progressive/k6-progressive.js

load-spike:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/spike-report.json bash $(K6_RUNNER_PATH) run --summary-export=$(RESULTS_DIR)/spike-summary.json load-tests/capacity/spike/k6-spike.js

load-sustained:
	mkdir -p $(RESULTS_DIR)
	BASE_URL=$(BASE_URL) CAPACITY_API_URL=$(CAPACITY_API_URL) SCENARIO_REPORT=$(RESULTS_DIR)/sustained-report.json bash $(K6_RUNNER_PATH) run --summary-export=$(RESULTS_DIR)/sustained-summary.json load-tests/capacity/sustained/k6-sustained.js

capacity-validation: load-normal load-progressive load-spike load-sustained

test-recovery:
	mkdir -p $(RECOVERY_RESULTS_DIR)
	NAMESPACE=$(NAMESPACE) RELEASE=$(RELEASE) KUBE_CONTEXT=$(KUBE_CONTEXT) RESULTS_DIR=$(RECOVERY_RESULTS_DIR) K6_RUNNER_PATH=$(K6_RUNNER_PATH) ALLOW_POD_DELETE=true bash scripts/capacity/run-recovery-test.sh

test-api-resilience:
	mkdir -p docs/evidence/member-3/validation
	NAMESPACE=$(NAMESPACE) KUBE_CONTEXT=$(KUBE_CONTEXT) RESULTS_DIR=docs/evidence/member-3/validation ALLOW_API_DISRUPTION=true bash scripts/capacity/run-api-resilience-test.sh

validation-evidence:
	$(TEST_PYTHON) scripts/capacity/summarize_validation_evidence.py --markdown docs/evidence/member-3/validation/validation-summary.md --output docs/evidence/member-3/validation/validation-summary.json

data-generate:
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/generate_synthetic_data.py --output-dir $(RAW_DIR) --source-commit $(SOURCE_COMMIT)

data-build:
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/build_dataset.py --raw-dir $(RAW_DIR) --processed-output $(PROCESSED_DIR)/$(DATASET_VERSION).csv --validation-report $(PROCESSED_DIR)/validation-report-v1.json --version-record $(PROCESSED_DIR)/dataset-v1.json --dataset-version $(DATASET_VERSION) --collection-date $(COLLECTION_DATE) --source-commit $(SOURCE_COMMIT) --feature-pipeline-version $(FEATURE_VERSION)

data-pipeline: data-generate data-build

data-validate:
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/validate_dataset.py --dataset $(PROCESSED_DIR)/$(DATASET_VERSION).csv

extract-prometheus:
	test -n "$(EXTRACT_START)" && test -n "$(EXTRACT_END)"
	mkdir -p $(RAW_EXPORT_DIR)
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/extract_prometheus_metrics.py --prometheus-url $(PROMETHEUS_URL) --queries ml/capacity/config/prometheus-queries.json --start $(EXTRACT_START) --end $(EXTRACT_END) --step $(EXTRACT_STEP) --scenario $(EXTRACT_SCENARIO) --output $(RAW_EXPORT_DIR)/$(EXTRACT_SCENARIO).csv --config-output $(RAW_EXPORT_DIR)/$(EXTRACT_SCENARIO)-collection.json

feature-build:
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/build_features.py --input $(PROCESSED_DIR)/$(DATASET_VERSION).csv --config $(FEATURE_CONFIG) --output $(FEATURE_DATASET) --metadata $(FEATURE_METADATA) --source-commit $(SOURCE_COMMIT)

baseline-evaluate: feature-build
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/evaluate_baseline.py --features $(FEATURE_DATASET) --baseline-config $(BASELINE_CONFIG) --policy-config $(REPLICA_POLICY_CONFIG) --output-dir $(BASELINE_EVALUATION_DIR)

baseline-validation: baseline-evaluate

model-train: baseline-evaluate
	PYTHONPATH=$(CURDIR)/ml/capacity/src $(TEST_PYTHON) ml/capacity/scripts/train_primary_model.py --features $(FEATURE_DATASET) --model-config $(MODEL_CONFIG) --policy-config $(REPLICA_POLICY_CONFIG) --baseline-metrics $(BASELINE_EVALUATION_DIR)/metrics.json --artifact-dir $(MODEL_ARTIFACT_DIR) --evaluation-dir $(PRIMARY_EVALUATION_DIR) --dataset-version $(DATASET_VERSION) --source-commit $(SOURCE_COMMIT)

model-validate: model-train

package-model: model-train
	$(TEST_PYTHON) scripts/capacity/package_model_artifacts.py --artifact-dir $(MODEL_ARTIFACT_DIR) --policy-config $(REPLICA_POLICY_CONFIG) --output-dir $(MODEL_PACKAGE_DIR)

config-validate:
	$(TEST_PYTHON) scripts/capacity/validate_configuration.py
