#!/bin/bash

# Script to build Lambda deployment package and layer
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Clean up old builds
print_message "$YELLOW" "Cleaning up old builds..."
rm -rf lambda-build/
rm -f lambda-deployment.zip
rm -f lambda-layer.zip

# Create build directory
mkdir -p lambda-build/layer/python
mkdir -p lambda-build/function

# Build Lambda Layer with dependencies
print_message "$YELLOW" "Building Lambda layer with dependencies..."
pip install -r requirements.txt -t lambda-build/layer/python/ --no-deps
cd lambda-build/layer
zip -r ../../lambda-layer.zip . -x "*.pyc" -x "*__pycache__*"
cd ../..
print_message "$GREEN" "✓ Lambda layer created: lambda-layer.zip"

# Build Lambda Function package
print_message "$YELLOW" "Building Lambda function package..."
cp -r src/ lambda-build/function/
cp -r config/ lambda-build/function/config/ || true  # Config might not exist yet

# Create a minimal config if it doesn't exist
if [ ! -f lambda-build/function/config/accounts.json ]; then
    mkdir -p lambda-build/function/config
    echo '{"accounts": {}}' > lambda-build/function/config/accounts.json
    print_message "$YELLOW" "⚠️  Created empty accounts.json - update this with your account configuration"
fi

cd lambda-build/function
zip -r ../../lambda-deployment.zip . -x "*.pyc" -x "*__pycache__*"
cd ../..
print_message "$GREEN" "✓ Lambda function package created: lambda-deployment.zip"

# Upload to S3 if bucket exists
if [ -n "${LAMBDA_DEPLOYMENT_BUCKET:-}" ]; then
    print_message "$YELLOW" "Uploading to S3 bucket: $LAMBDA_DEPLOYMENT_BUCKET"
    aws s3 cp lambda-deployment.zip "s3://$LAMBDA_DEPLOYMENT_BUCKET/lambda-deployment.zip"
    aws s3 cp lambda-layer.zip "s3://$LAMBDA_DEPLOYMENT_BUCKET/lambda-layer.zip"
    print_message "$GREEN" "✓ Uploaded to S3"
else
    print_message "$YELLOW" "ℹ️  Set LAMBDA_DEPLOYMENT_BUCKET environment variable to automatically upload to S3"
fi

# Clean up build directory
rm -rf lambda-build/

print_message "$GREEN" "✅ Lambda build complete!"
print_message "$YELLOW" "Next steps:"
print_message "$YELLOW" "1. Update config/accounts.json with your AWS accounts"
print_message "$YELLOW" "2. Run 'terraform apply' to deploy the Lambda function"