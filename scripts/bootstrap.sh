#!/usr/bin/env bash
# Run once before `terraform init` to create the S3 backend bucket.
# Make executable with: chmod +x scripts/bootstrap.sh
set -euo pipefail

BUCKET_NAME="deploytracker-tfstate-378202225330"
REGION="eu-west-3"

echo "Creating S3 bucket for Terraform state..."

if aws s3 ls "s3://${BUCKET_NAME}" 2>/dev/null; then
  echo "Bucket ${BUCKET_NAME} already exists, skipping."
else
  aws s3api create-bucket \
    --bucket "${BUCKET_NAME}" \
    --region "${REGION}" \
    --create-bucket-configuration LocationConstraint="${REGION}"

  aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --versioning-configuration Status=Enabled

  aws s3api put-bucket-encryption \
    --bucket "${BUCKET_NAME}" \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }]
    }'

  aws s3api put-public-access-block \
    --bucket "${BUCKET_NAME}" \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

  echo "Bucket ${BUCKET_NAME} created successfully."
fi

echo "Bootstrap complete. You can now run: cd infra/terraform && terraform init"
