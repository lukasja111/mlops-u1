#!/usr/bin/env bash
set -eu
OWNER=$(gh api user --jq '.login | ascii_downcase')
SHA=$(git rev-parse --short=8 HEAD)
LOCAL=mlops-u1/train:sha-$SHA
REMOTE=ghcr.io/$OWNER/mlops-u1/train:sha-$SHA

docker image inspect "$LOCAL" >/dev/null
trivy image --scanners vuln --severity CRITICAL --exit-code 1 "$LOCAL"
gh auth token | docker login ghcr.io -u "$OWNER" --password-stdin
docker tag "$LOCAL" "$REMOTE"
docker push "$REMOTE"
echo "digest: $(docker inspect --format '{{index .RepoDigests 0}}' "$REMOTE")"
echo "Then make the package public: GitHub -> Packages -> mlops-u1/train -> Package settings -> Public"
