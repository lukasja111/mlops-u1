#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${MLFLOW_TRACKING_URI:?export MLFLOW_TRACKING_URI and the trainer credentials first}"
: "${MLFLOW_TRACKING_USERNAME:?export the trainer credentials first}"

if [ "${1:-}" = rollback ]; then
  python scripts/promote.py rollback
else
  ruff check .
  python -m pytest -q
  dvc repro
  python scripts/gate.py || { echo "quality gate failed: nothing registered or deployed"; exit 1; }
  registered=$(python scripts/promote.py register)
  echo "$registered"
  if grep -qx 'new=true' <<<"$registered"; then
    python scripts/promote.py promote --version "$(sed -n 's/^version=//p' <<<"$registered")"
  else
    echo "run already registered: @champion stays as it is"
  fi
fi

version=$(python scripts/promote.py current | sed -n 's/^version=//p')
sed -i "s|MODEL_VERSION=.*|MODEL_VERSION=$version|" k8s/serving/kustomization.yaml
kubectl apply -k k8s/serving
kubectl -n mlops-u1 rollout status deploy/api --timeout=300s
node=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
image=$(sed -n 's/.*IMAGE_TAG=//p' k8s/serving/kustomization.yaml)
python scripts/load_test.py "http://$node:30800" --expect-version "$version" --expect-image "$image" --timeout 120
