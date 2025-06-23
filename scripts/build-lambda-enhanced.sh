#!/bin/bash
set -e

echo "Building enhanced Lambda deployment packages..."

# Clean up old builds
rm -rf lambda-build/
rm -f lambda-deployment.zip lambda-layer.zip

# Create build directories
mkdir -p lambda-build/lambda
mkdir -p lambda-build/layer/python

# Copy source code
cp -r src/* lambda-build/lambda/
cp -r config lambda-build/lambda/

# Remove test files and __pycache__
find lambda-build/lambda -name "*test*" -delete
find lambda-build/lambda -name "__pycache__" -type d -exec rm -rf {} +
find lambda-build/lambda -name "*.pyc" -delete

# Create requirements for layer
cat > lambda-build/layer-requirements.txt << 'REQ'
boto3>=1.26.0
pandas>=1.5.0
tabulate>=0.9.0
REQ

# Install dependencies for layer
pip install -r lambda-build/layer-requirements.txt -t lambda-build/layer/python/ --no-deps

# Clean up unnecessary files from layer
find lambda-build/layer -name "*.pyc" -delete
find lambda-build/layer -name "*__pycache__*" -type d -exec rm -rf {} +
find lambda-build/layer -name "*.dist-info" -type d -exec rm -rf {} +
find lambda-build/layer -name "tests" -type d -exec rm -rf {} +
find lambda-build/layer -name "test" -type d -exec rm -rf {} +

# Create deployment packages
cd lambda-build/lambda
zip -r ../../lambda-deployment.zip . -x "*.pyc" "*__pycache__*" "*.pytest_cache*"
cd ../..

cd lambda-build/layer
zip -r ../../lambda-layer.zip . -x "*.pyc" "*__pycache__*"
cd ../..

echo "Lambda packages built successfully:"
echo "  - lambda-deployment.zip"
echo "  - lambda-layer.zip"
