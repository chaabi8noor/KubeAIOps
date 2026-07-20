NAMESPACE ?= kubeaiops
RELEASE ?= capacity-api
KIND_CLUSTER ?= kubeaiops
CHART ?= helm/capacity-api
IMAGE_TAG ?= dev
BASE_URL ?= http://127.0.0.1:8001
CAPACITY_API_URL ?= http://127.0.0.1:8000
TEST_PYTHON ?= $(CURDIR)/.member3-venv/bin/python

.PHONY: setup-test-env test helm-lint helm-template images kind-load deploy-local verify-local k6-smoke

setup-test-env:
	python3 -m venv $(CURDIR)/.member3-venv
	$(TEST_PYTHON) -m pip install --disable-pip-version-check -r services/capacity-api/requirements-dev.txt -r services/demo-workload/requirements-dev.txt

test:
	cd services/capacity-api && $(TEST_PYTHON) -m pytest -q
	cd services/demo-workload && $(TEST_PYTHON) -m pytest -q

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
