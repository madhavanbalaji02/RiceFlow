#!/usr/bin/env bash
set -euo pipefail
mkdir -p containers
image=$(cat containers/base-image.txt)
docker pull --platform linux/amd64 "$image"
base=$(docker image inspect "$image" --format '{{index .RepoDigests 0}}')
printf '%s\n' "$base" > containers/base-image.txt
docker build --platform linux/amd64 --build-arg "BASE_IMAGE=$base" -f containers/Dockerfile -t riceflow:0.1.0 .
docker image inspect riceflow:0.1.0 --format '{{.Id}}' > containers/local-image-id.txt
printf '%s\n' "$base" > containers/base-image.txt
# A local image ID is NOT a registry digest. Record RepoDigest after an explicitly authorized push.
