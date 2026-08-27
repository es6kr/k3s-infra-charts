# Load .env then .env.local (local overrides)
-include .env
-include .env.local
export

.PHONY: all package lint unittest template test act act-test install-unittest clean force-push helm-install helm-upgrade index

all: lint unittest

# Package all charts
package:
	helm package charts/* --destination download

# Lint all charts
lint:
	helm lint charts/host-ip-service
	helm lint charts/cluster-issuers
	helm lint charts/openclaw-agent

# Run unit tests
unittest:
	helm unittest charts/host-ip-service
	helm unittest charts/openclaw-agent

# Template charts for validation
template:
	helm template test-release charts/host-ip-service \
		--set namespace=test \
		--set endpoint.name=test-host \
		--set endpoint.ip=10.0.0.1 \
		--set 'endpoint.ports[0].name=http' \
		--set 'endpoint.ports[0].port=80'
	helm template test-release charts/openclaw-agent

# Run all tests
test: lint unittest template

# Run CI workflow locally with act
act:
	act -j unittest

# Run all test.yaml jobs with act (pages.yaml requires GitHub)
act-test:
	act -W .github/workflows/test.yaml push

# Install helm-unittest plugin
install-unittest:
	helm plugin install https://github.com/helm-unittest/helm-unittest.git || true

# Clean generated files
clean:
	rm -rf charts/*/charts
	rm -rf charts/*/*.tgz

force-push:
	git push origin main -f

helm-install:
	helm install docker-host-ip-service charts/host-ip-service -f test-values.yaml

helm-upgrade:
	helm upgrade docker-host-ip-service charts/host-ip-service -f test-values.yaml

index:
	helm repo index download --url https://github.com/es6kr/nginx-cert-charts/releases/download
