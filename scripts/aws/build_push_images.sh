#!/usr/bin/env bash
# Build linux/arm64 service images and publish them to Amazon ECR.
#
# Usage:
#   ./scripts/aws/build_push_images.sh
#   ./scripts/aws/build_push_images.sh api
#
set -euo pipefail

PROFILE="${AWS_PROFILE:-default}"
REGION="${AWS_REGION:-ap-southeast-2}"
ACCOUNT="$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

cd "$(dirname "$0")/../.."

echo "==> ECR login…"
aws ecr get-login-password --profile "$PROFILE" --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null

build_push() {
  local svc="$1" dockerfile="$2"
  echo ""
  echo "==> [$svc] building (linux/arm64, default driver)…"
  # Build into the local image store before publishing to ECR.
  docker build \
    --platform linux/arm64 \
    -f "$dockerfile" \
    -t "${REGISTRY}/auckland-hospital/${svc}:latest" \
    .
  echo "==> [$svc] pushing to ECR…"
  docker push "${REGISTRY}/auckland-hospital/${svc}:latest"
}

TARGET="${1:-all}"

if [ "$TARGET" = "all" ] || [ "$TARGET" = "api" ]; then
  build_push api docker/api/Dockerfile
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "worker" ]; then
  # The worker uses the API image with a different service entrypoint.
  echo ""
  echo "==> [worker] retagging api image…"
  docker tag "${REGISTRY}/auckland-hospital/api:latest" "${REGISTRY}/auckland-hospital/worker:latest"
  docker push "${REGISTRY}/auckland-hospital/worker:latest"
fi
if [ "$TARGET" = "all" ] || [ "$TARGET" = "voice" ]; then
  build_push voice docker/voice/Dockerfile
fi

echo ""
echo "Images published to ECR."
