#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
ENVIRONMENT="production"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="aws-inventory"

# Parse arguments
NOTIFICATION_EMAIL="$1"
if [ -z "$NOTIFICATION_EMAIL" ]; then
    echo -e "${RED}Error: Notification email required${NC}"
    echo "Usage: $0 <notification-email> [environment] [stack-name]"
    exit 1
fi

if [ -n "$2" ]; then
    ENVIRONMENT="$2"
fi

if [ -n "$3" ]; then
    STACK_NAME="$3"
fi

echo -e "${GREEN}AWS Multi-Account Inventory Deployment${NC}"
echo "Environment: $ENVIRONMENT"
echo "Stack Name: $STACK_NAME"
echo "Region: $AWS_REGION"
echo "Notification Email: $NOTIFICATION_EMAIL"
echo ""

# Function to check command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed${NC}"
        exit 1
    fi
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
check_command aws
check_command python3
check_command pip3
check_command zip

# Verify AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: $AWS_ACCOUNT_ID"

# Create deployment bucket name
DEPLOYMENT_BUCKET="${STACK_NAME}-deployment-${AWS_ACCOUNT_ID}"

# Step 1: Create deployment S3 bucket if it doesn't exist
echo -e "\n${YELLOW}Step 1: Creating deployment S3 bucket...${NC}"
if aws s3 ls "s3://${DEPLOYMENT_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
    aws s3 mb "s3://${DEPLOYMENT_BUCKET}" --region "$AWS_REGION"
    
    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "${DEPLOYMENT_BUCKET}" \
        --versioning-configuration Status=Enabled
    
    # Block public access
    aws s3api put-public-access-block \
        --bucket "${DEPLOYMENT_BUCKET}" \
        --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    
    echo -e "${GREEN}Created deployment bucket: ${DEPLOYMENT_BUCKET}${NC}"
else
    echo "Deployment bucket already exists: ${DEPLOYMENT_BUCKET}"
fi

# Step 2: Install Python dependencies
echo -e "\n${YELLOW}Step 2: Installing Python dependencies...${NC}"
cd "$PROJECT_ROOT"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pandas tabulate  # Additional dependencies for enhanced features

# Step 3: Run tests
echo -e "\n${YELLOW}Step 3: Running unit tests...${NC}"
if python -m pytest tests/unit/test_enhanced_collector.py -v; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Tests failed! Fix issues before deploying.${NC}"
    exit 1
fi

# Step 4: Build Lambda deployment packages
echo -e "\n${YELLOW}Step 4: Building Lambda deployment packages...${NC}"

# Clean up old builds
rm -rf lambda-build/
rm -f lambda-deployment.zip lambda-layer.zip

# Create build directory
mkdir -p lambda-build/lambda
mkdir -p lambda-build/layer/python

# Copy source code for main Lambda
cp -r src/* lambda-build/lambda/
cp -r config lambda-build/lambda/

# Create Lambda deployment package
cd lambda-build/lambda
zip -r ../../lambda-deployment.zip . -x "*.pyc" "*__pycache__*" "*.pytest_cache*"
cd ../..

# Create Lambda layer with dependencies
pip install -r requirements.txt -t lambda-build/layer/python/
pip install pandas tabulate -t lambda-build/layer/python/

# Remove unnecessary files from layer
find lambda-build/layer -name "*.pyc" -delete
find lambda-build/layer -name "*__pycache__*" -type d -exec rm -rf {} +
find lambda-build/layer -name "*.dist-info" -type d -exec rm -rf {} +
find lambda-build/layer -name "tests" -type d -exec rm -rf {} +

# Create layer package
cd lambda-build/layer
zip -r ../../lambda-layer.zip . -x "*.pyc" "*__pycache__*"
cd ../..

echo -e "${GREEN}Lambda packages built successfully${NC}"

# Step 5: Upload packages to S3
echo -e "\n${YELLOW}Step 5: Uploading Lambda packages to S3...${NC}"
aws s3 cp lambda-deployment.zip "s3://${DEPLOYMENT_BUCKET}/" --region "$AWS_REGION"
aws s3 cp lambda-layer.zip "s3://${DEPLOYMENT_BUCKET}/" --region "$AWS_REGION"

# Step 6: Deploy CloudFormation stack
echo -e "\n${YELLOW}Step 6: Deploying CloudFormation stack...${NC}"

# Check if stack exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &> /dev/null; then
    STACK_ACTION="update-stack"
    WAIT_ACTION="stack-update-complete"
    echo "Updating existing stack..."
else
    STACK_ACTION="create-stack"
    WAIT_ACTION="stack-create-complete"
    echo "Creating new stack..."
fi

# Deploy stack
aws cloudformation $STACK_ACTION \
    --stack-name "$STACK_NAME" \
    --template-body file://cloudformation/complete-infrastructure.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
        ParameterKey=NotificationEmail,ParameterValue="$NOTIFICATION_EMAIL" \
        ParameterKey=DeploymentBucket,ParameterValue="$DEPLOYMENT_BUCKET" \
        ParameterKey=CostAlertThreshold,ParameterValue=10000 \
        ParameterKey=EnableEnhancedMonitoring,ParameterValue=true \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION"

# Wait for stack to complete
echo "Waiting for stack operation to complete..."
if aws cloudformation wait $WAIT_ACTION --stack-name "$STACK_NAME" --region "$AWS_REGION"; then
    echo -e "${GREEN}Stack deployed successfully!${NC}"
else
    echo -e "${RED}Stack deployment failed!${NC}"
    exit 1
fi

# Step 7: Update Lambda function code
echo -e "\n${YELLOW}Step 7: Updating Lambda function code...${NC}"

# Get Lambda function name from stack outputs
LAMBDA_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionArn`].OutputValue' \
    --output text | cut -d: -f7)

if [ -n "$LAMBDA_FUNCTION" ]; then
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION" \
        --s3-bucket "$DEPLOYMENT_BUCKET" \
        --s3-key lambda-deployment.zip \
        --region "$AWS_REGION"
    
    echo -e "${GREEN}Lambda function code updated${NC}"
fi

# Step 8: Deploy sample configuration
echo -e "\n${YELLOW}Step 8: Creating sample configuration...${NC}"

# Create sample config if it doesn't exist
if [ ! -f "config/accounts.json" ]; then
    cp config/enhanced_accounts.json config/accounts.json
    echo -e "${YELLOW}Created sample configuration at config/accounts.json${NC}"
    echo -e "${YELLOW}Please update with your actual AWS account IDs${NC}"
fi

# Step 9: Display deployment information
echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo ""

# Get stack outputs
echo "Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Get important resource names
DYNAMODB_TABLE=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`DynamoDBTableName`].OutputValue' \
    --output text)

SNS_TOPIC=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`SNSTopicArn`].OutputValue' \
    --output text)

REPORTS_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ReportsBucketName`].OutputValue' \
    --output text)

DASHBOARD_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
    --output text)

# Step 10: Create deployment summary
echo -e "\n${YELLOW}Creating deployment summary...${NC}"

cat > deployment-summary.md << EOF
# AWS Multi-Account Inventory Deployment Summary

**Deployment Date:** $(date)
**Environment:** $ENVIRONMENT
**Stack Name:** $STACK_NAME
**Region:** $AWS_REGION
**AWS Account:** $AWS_ACCOUNT_ID

## Resources Created

- **DynamoDB Table:** $DYNAMODB_TABLE
- **Lambda Function:** $LAMBDA_FUNCTION
- **SNS Topic:** $SNS_TOPIC
- **Reports Bucket:** $REPORTS_BUCKET
- **CloudWatch Dashboard:** $DASHBOARD_URL

## Next Steps

1. **Deploy IAM Roles in Target Accounts:**
   \`\`\`bash
   cd terraform/target-account-role
   terraform init
   terraform apply -var="central_account_id=$AWS_ACCOUNT_ID"
   \`\`\`

2. **Update Account Configuration:**
   Edit \`config/accounts.json\` with your AWS account details

3. **Test Lambda Function:**
   \`\`\`bash
   aws lambda invoke \\
     --function-name $LAMBDA_FUNCTION \\
     --payload '{"action": "collect"}' \\
     output.json
   \`\`\`

4. **Query Inventory:**
   \`\`\`bash
   python src/query/enhanced_inventory_query.py --action summary
   \`\`\`

## Monitoring

- CloudWatch Dashboard: $DASHBOARD_URL
- SNS Alerts will be sent to: $NOTIFICATION_EMAIL

## Cost Optimization

The system will automatically:
- Send daily cost analysis reports
- Alert when monthly costs exceed \$10,000
- Identify idle and oversized resources
- Check for security compliance weekly

EOF

echo -e "${GREEN}Deployment summary saved to deployment-summary.md${NC}"

# Final instructions
echo -e "\n${GREEN}=== Deployment Successful! ===${NC}"
echo ""
echo "Next steps:"
echo "1. Confirm SNS subscription in your email ($NOTIFICATION_EMAIL)"
echo "2. Deploy IAM roles in target accounts (see deployment-summary.md)"
echo "3. Update config/accounts.json with your AWS accounts"
echo "4. Test the Lambda function"
echo ""
echo "For detailed instructions, see deployment-summary.md"

# Deactivate virtual environment
deactivate