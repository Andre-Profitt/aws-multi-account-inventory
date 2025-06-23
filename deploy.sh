#!/bin/bash

# AWS Multi-Account Inventory Deployment Script
# This script automates the deployment of the inventory system

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="${STACK_NAME:-aws-inventory-system}"
REGION="${AWS_REGION:-us-east-1}"
ARTIFACTS_BUCKET_PREFIX="aws-inventory-artifacts"
CONFIG_FILE="${CONFIG_FILE:-config/accounts.json}"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check for AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    # Check for Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3."
        exit 1
    fi
    
    # Check for pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 not found. Please install pip3."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi
    
    # Check for required files
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Configuration file not found: $CONFIG_FILE"
        print_status "Creating example configuration file..."
        cp config/accounts.json.example "$CONFIG_FILE"
        print_warning "Please update $CONFIG_FILE with your account information."
        exit 1
    fi
    
    print_success "Prerequisites check passed."
}

# Function to validate parameters
get_parameters() {
    print_status "Gathering deployment parameters..."
    
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_status "Account ID: $ACCOUNT_ID"
    
    # Get organization ID
    ORGANIZATION_ID=$(aws organizations describe-organization --query Organization.Id --output text 2>/dev/null || echo "")
    if [ -n "$ORGANIZATION_ID" ]; then
        print_status "Organization ID: $ORGANIZATION_ID"
    else
        print_warning "Not in an AWS Organization. Cross-account features may be limited."
    fi
    
    # Get email for notifications
    if [ -z "$EMAIL_ADDRESS" ]; then
        read -p "Enter email address for notifications: " EMAIL_ADDRESS
    fi
    
    # Get Slack webhook (optional)
    if [ -z "$SLACK_WEBHOOK_URL" ]; then
        read -p "Enter Slack webhook URL (optional, press Enter to skip): " SLACK_WEBHOOK_URL
    fi
    
    # Get monthly cost threshold
    if [ -z "$MONTHLY_COST_THRESHOLD" ]; then
        read -p "Enter monthly cost threshold for alerts (default: 10000): " MONTHLY_COST_THRESHOLD
        MONTHLY_COST_THRESHOLD=${MONTHLY_COST_THRESHOLD:-10000}
    fi
    
    # External ID for role assumption
    EXTERNAL_ID="${EXTERNAL_ID:-inventory-collector}"
    
    print_success "Parameters gathered."
}

# Function to create S3 artifacts bucket
create_artifacts_bucket() {
    ARTIFACTS_BUCKET="${ARTIFACTS_BUCKET_PREFIX}-${REGION}"
    print_status "Creating artifacts bucket: $ARTIFACTS_BUCKET"
    
    # Create bucket
    if aws s3 ls "s3://$ARTIFACTS_BUCKET" 2>&1 | grep -q 'NoSuchBucket'; then
        if [ "$REGION" == "us-east-1" ]; then
            aws s3 mb "s3://$ARTIFACTS_BUCKET"
        else
            aws s3 mb "s3://$ARTIFACTS_BUCKET" --region "$REGION"
        fi
        
        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "$ARTIFACTS_BUCKET" \
            --versioning-configuration Status=Enabled
        
        # Enable encryption
        aws s3api put-bucket-encryption \
            --bucket "$ARTIFACTS_BUCKET" \
            --server-side-encryption-configuration '{
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }]
            }'
        
        print_success "Artifacts bucket created."
    else
        print_status "Artifacts bucket already exists."
    fi
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    pip install -r requirements.txt
    
    print_success "Dependencies installed."
}

# Function to run tests
run_tests() {
    print_status "Running unit tests..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Run pytest
    if pytest tests/unit -v; then
        print_success "All tests passed."
    else
        print_error "Tests failed. Please fix issues before deploying."
        exit 1
    fi
}

# Function to package Lambda function
package_lambda() {
    print_status "Packaging Lambda function..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    LAMBDA_PACKAGE="$TEMP_DIR/lambda-package.zip"
    
    # Copy source code
    cp -r src/* "$TEMP_DIR/"
    
    # Create deployment package
    cd "$TEMP_DIR"
    zip -r "$LAMBDA_PACKAGE" . -x "*.pyc" -x "__pycache__/*"
    cd - > /dev/null
    
    # Upload to S3
    aws s3 cp "$LAMBDA_PACKAGE" "s3://$ARTIFACTS_BUCKET/lambda/inventory-collector.zip"
    
    # Clean up
    rm -rf "$TEMP_DIR"
    
    print_success "Lambda function packaged and uploaded."
}

# Function to package Lambda layer
package_layer() {
    print_status "Packaging Lambda layer..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    LAYER_DIR="$TEMP_DIR/python"
    mkdir -p "$LAYER_DIR"
    
    # Install dependencies to layer directory
    pip install -r requirements.txt -t "$LAYER_DIR" --no-deps
    
    # Remove unnecessary files
    find "$LAYER_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$LAYER_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$LAYER_DIR" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    
    # Create layer package
    cd "$TEMP_DIR"
    zip -r layer.zip python/
    cd - > /dev/null
    
    # Upload to S3
    aws s3 cp "$TEMP_DIR/layer.zip" "s3://$ARTIFACTS_BUCKET/layers/dependencies.zip"
    
    # Clean up
    rm -rf "$TEMP_DIR"
    
    print_success "Lambda layer packaged and uploaded."
}

# Function to upload CloudFormation templates
upload_templates() {
    print_status "Uploading CloudFormation templates..."
    
    # Upload main template
    aws s3 cp infrastructure/cloudformation.yaml \
        "s3://$ARTIFACTS_BUCKET/templates/main.yaml"
    
    # Upload member account role template
    aws s3 cp infrastructure/member-account-role.yaml \
        "s3://$ARTIFACTS_BUCKET/templates/member-account-role.yaml"
    
    print_success "Templates uploaded."
}

# Function to deploy CloudFormation stack
deploy_stack() {
    print_status "Deploying CloudFormation stack..."
    
    # Prepare parameters
    PARAMETERS="
        ParameterKey=OrganizationId,ParameterValue=${ORGANIZATION_ID:-none}
        ParameterKey=ExternalId,ParameterValue=$EXTERNAL_ID
        ParameterKey=MonthlyCostThreshold,ParameterValue=$MONTHLY_COST_THRESHOLD
        ParameterKey=EmailAddress,ParameterValue=$EMAIL_ADDRESS
        ParameterKey=SlackWebhookUrl,ParameterValue=${SLACK_WEBHOOK_URL:-}
    "
    
    # Deploy stack
    aws cloudformation deploy \
        --template-file infrastructure/cloudformation.yaml \
        --stack-name "$STACK_NAME" \
        --parameter-overrides $PARAMETERS \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --no-fail-on-empty-changeset
    
    print_success "CloudFormation stack deployed."
}

# Function to deploy member account roles
deploy_member_roles() {
    print_status "Deploying member account roles..."
    
    # Read accounts from config
    ACCOUNTS=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    config = json.load(f)
    for name, account in config.get('accounts', {}).items():
        if account.get('enabled', True):
            print(f\"{name}:{account['account_id']}\")
    ")
    
    # Deploy role to each account
    for ACCOUNT_INFO in $ACCOUNTS; do
        ACCOUNT_NAME=$(echo "$ACCOUNT_INFO" | cut -d: -f1)
        ACCOUNT_ID=$(echo "$ACCOUNT_INFO" | cut -d: -f2)
        
        print_status "Deploying role to $ACCOUNT_NAME ($ACCOUNT_ID)..."
        
        # Generate CloudFormation command for member account
        cat << EOF

To deploy the inventory role in account $ACCOUNT_NAME ($ACCOUNT_ID), run:

aws cloudformation deploy \\
    --template-file infrastructure/member-account-role.yaml \\
    --stack-name aws-inventory-role \\
    --parameter-overrides \\
        MasterAccountId=$ACCOUNT_ID \\
        ExternalId=$EXTERNAL_ID \\
        OrganizationId=${ORGANIZATION_ID:-} \\
    --capabilities CAPABILITY_NAMED_IAM \\
    --profile $ACCOUNT_NAME  # Update with correct profile name

EOF
    done
    
    print_warning "Please deploy the role template to each member account."
}

# Function to create initial configuration
create_config() {
    print_status "Creating Lambda configuration..."
    
    # Create config directory in Lambda package
    CONFIG_DIR="lambda-config"
    mkdir -p "$CONFIG_DIR"
    
    # Copy configuration file
    cp "$CONFIG_FILE" "$CONFIG_DIR/accounts.json"
    
    # Package and upload
    cd "$CONFIG_DIR"
    zip -r config.zip accounts.json
    aws s3 cp config.zip "s3://$ARTIFACTS_BUCKET/config/accounts.json.zip"
    cd - > /dev/null
    
    # Clean up
    rm -rf "$CONFIG_DIR"
    
    print_success "Configuration uploaded."
}

# Function to run initial collection
run_initial_collection() {
    print_status "Running initial inventory collection..."
    
    # Get Lambda function name
    LAMBDA_FUNCTION=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionArn`].OutputValue' \
        --output text \
        --region "$REGION")
    
    if [ -n "$LAMBDA_FUNCTION" ]; then
        # Invoke Lambda function
        aws lambda invoke \
            --function-name "$LAMBDA_FUNCTION" \
            --payload '{"action": "collect"}' \
            --region "$REGION" \
            response.json
        
        # Check response
        if grep -q "Successfully collected" response.json; then
            print_success "Initial collection completed."
            cat response.json | python3 -m json.tool
        else
            print_error "Initial collection failed."
            cat response.json
        fi
        
        rm -f response.json
    else
        print_warning "Could not find Lambda function. Please run collection manually."
    fi
}

# Function to display deployment summary
display_summary() {
    print_status "Deployment Summary"
    echo "=================="
    
    # Get stack outputs
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs' \
        --region "$REGION" 2>/dev/null || echo "[]")
    
    if [ "$OUTPUTS" != "[]" ]; then
        echo "$OUTPUTS" | python3 -c "
import json, sys
outputs = json.load(sys.stdin)
for output in outputs:
    print(f\"{output['OutputKey']}: {output['OutputValue']}\")
        "
    fi
    
    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Deploy the member account role to each AWS account"
    echo "2. Update the configuration file as needed"
    echo "3. Monitor the CloudWatch dashboard for metrics"
    echo "4. Check your email for SNS subscription confirmation"
}

# Main deployment flow
main() {
    echo "AWS Multi-Account Inventory System Deployment"
    echo "============================================"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Get parameters
    get_parameters
    
    # Create artifacts bucket
    create_artifacts_bucket
    
    # Install dependencies
    install_dependencies
    
    # Run tests
    if [ "${SKIP_TESTS:-false}" != "true" ]; then
        run_tests
    else
        print_warning "Skipping tests (SKIP_TESTS=true)"
    fi
    
    # Package Lambda function and layer
    package_lambda
    package_layer
    
    # Upload templates
    upload_templates
    
    # Create configuration
    create_config
    
    # Deploy stack
    deploy_stack
    
    # Display member account role deployment instructions
    deploy_member_roles
    
    # Run initial collection (optional)
    if [ "${RUN_INITIAL_COLLECTION:-false}" == "true" ]; then
        run_initial_collection
    fi
    
    # Display summary
    display_summary
}

# Run main function
main "$@"