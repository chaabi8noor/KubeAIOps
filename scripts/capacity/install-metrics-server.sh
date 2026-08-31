#!/usr/bin/env sh
set -eu

# Local Kind-only helper. The insecure kubelet TLS flag is not for shared or production clusters.
metrics_server_version="${METRICS_SERVER_VERSION:-v0.8.1}"
manifest_url="https://github.com/kubernetes-sigs/metrics-server/releases/download/${metrics_server_version}/components.yaml"

kubectl apply -f "${manifest_url}"

if ! kubectl -n kube-system get deployment metrics-server -o jsonpath='{.spec.template.spec.containers[0].args[*]}' | grep -q -- '--kubelet-insecure-tls'; then
  kubectl -n kube-system patch deployment metrics-server --type=json --patch='[
    {
      "op": "add",
      "path": "/spec/template/spec/containers/0/args/-",
      "value": "--kubelet-insecure-tls"
    }
  ]'
fi

kubectl -n kube-system rollout status deployment/metrics-server --timeout=180s
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes
