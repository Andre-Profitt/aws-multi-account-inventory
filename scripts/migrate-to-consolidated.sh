#!/bin/bash
set -e

# Script to migrate to consolidated version with enhanced features
# This preserves the best of both Terraform infrastructure and enhanced features

echo "AWS Multi-Account Inventory - Migration to Consolidated Version"
echo "=============================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "Makefile" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# Step 1: Backup current files
echo -e "${YELLOW}Step 1: Creating backup of current files...${NC}"
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
cp -r terraform/ backups/$(date +%Y%m%d_%H%M%S)/terraform_backup
cp -r src/ backups/$(date +%Y%m%d_%H%M%S)/src_backup
echo -e "${GREEN}Backup completed${NC}"

# Step 2: Clean up merge conflicts
echo -e "\n${YELLOW}Step 2: Cleaning up merge conflicts...${NC}"

# Abort the current merge
git merge --abort || true

# Step 3: Create consolidated Terraform configuration
echo -e "\n${YELLOW}Step 3: Setting up consolidated Terraform configuration...${NC}"

# Replace the conflicted main.tf with consolidated version
mv terraform/main_consolidated.tf terraform/main.tf
mv terraform/variables_consolidated.tf terraform/variables.tf

# Create outputs.tf
cat > terraform/outputs.tf << 'EOF'
output "dynamodb_table_name" {
  description = "Name of the DynamoDB inventory table"
  value       = aws_dynamodb_table.inventory.name
}

output "lambda_function_arn" {
  description = "ARN of the inventory collector Lambda function"
  value       = aws_lambda_function.inventory_collector.arn
}

output "lambda_function_name" {
  description = "Name of the inventory collector Lambda function"
  value       = aws_lambda_function.inventory_collector.function_name
}

output "sns_topic_arn" {
  description = "ARN of the SNS alert topic"
  value       = aws_sns_topic.alerts.arn
}

output "reports_bucket_name" {
  description = "Name of the S3 reports bucket"
  value       = aws_s3_bucket.reports.id
}

output "dashboard_url" {
  description = "CloudWatch Dashboard URL"
  value       = var.enable_monitoring ? "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${var.stack_name}-inventory" : "Monitoring disabled"
}

output "deployment_instructions" {
  description = "Next steps for deployment"
  value       = <<-EOT
    Stack deployed successfully! Next steps:
    
    1. Deploy IAM roles in target accounts:
       cd terraform/target-account-role
       terraform apply -var="central_account_id=${data.aws_caller_identity.current.account_id}"
    
    2. Configure accounts in config/accounts.json
    
    3. Test the deployment:
       aws lambda invoke \
         --function-name ${aws_lambda_function.inventory_collector.function_name} \
         --payload '{"action": "collect"}' \
         output.json
  EOT
}
EOF

# Step 4: Create consolidated Makefile
echo -e "\n${YELLOW}Step 4: Creating consolidated Makefile...${NC}"

cat > Makefile << 'EOF'
.PHONY: help install test deploy deploy-plan deploy-iam collect query clean validate build-lambda

help:
	@echo "AWS Multi-Account Inventory - Enhanced Edition"
	@echo "make install       - Install dependencies"
	@echo "make validate      - Validate Terraform configuration"
	@echo "make build-lambda  - Build Lambda deployment package"
	@echo "make deploy-plan   - Show Terraform deployment plan"
	@echo "make deploy        - Deploy infrastructure with Terraform"
	@echo "make deploy-iam    - Deploy IAM roles in target accounts"
	@echo "make collect       - Run inventory collection locally"
	@echo "make query         - Query inventory summary"
	@echo "make query-cost    - Run cost analysis"
	@echo "make query-security - Check security compliance"
	@echo "make test          - Run unit tests"
	@echo "make clean         - Clean up generated files"

install:
	pip install -r requirements.txt
	pip install pandas tabulate pytest moto
	@echo "Checking Terraform installation..."
	@terraform version || echo "Please install Terraform: https://www.terraform.io/downloads"

validate:
	cd terraform && terraform init && terraform validate

build-lambda:
	@echo "Building Lambda deployment packages..."
	@chmod +x scripts/build-lambda-enhanced.sh
	@./scripts/build-lambda-enhanced.sh

deploy-plan: build-lambda
	cd terraform && terraform init && terraform plan

deploy: build-lambda
	cd terraform && terraform init && terraform apply

deploy-iam:
	@echo "To deploy IAM roles in target accounts:"
	@echo "1. cd terraform/target-account-role"
	@echo "2. terraform init"
	@echo "3. terraform apply -var=\"central_account_id=YOUR_CENTRAL_ACCOUNT_ID\""

collect:
	python src/collector/enhanced_main.py --config config/accounts.json

query:
	python -m src.query.enhanced_inventory_query --action summary

query-cost:
	python -m src.query.enhanced_inventory_query --action cost

query-security:
	python -m src.query.enhanced_inventory_query --action security

query-export:
	python -m src.query.enhanced_inventory_query --action export --output inventory-export.csv

test:
	python -m pytest tests/unit/test_enhanced_collector.py -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf lambda-build/
	rm -f lambda-deployment.zip
	rm -f lambda-layer.zip
EOF

# Step 5: Create enhanced Lambda build script
echo -e "\n${YELLOW}Step 5: Creating enhanced Lambda build script...${NC}"

cat > scripts/build-lambda-enhanced.sh << 'EOF'
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
EOF

chmod +x scripts/build-lambda-enhanced.sh

# Step 6: Update requirements.txt
echo -e "\n${YELLOW}Step 6: Updating requirements.txt...${NC}"

cat > requirements.txt << 'EOF'
boto3>=1.26.0
click>=8.0.0
pandas>=1.5.0
tabulate>=0.9.0
pytest>=7.0.0
moto>=4.0.0
EOF

# Step 7: Create consolidated config example
echo -e "\n${YELLOW}Step 7: Creating consolidated config example...${NC}"

cat > config/accounts.json.example << 'EOF'
{
  "accounts": {
    "production": {
      "account_id": "123456789012",
      "role_name": "InventoryRole",
      "tags": {
        "Environment": "Production",
        "Department": "Engineering"
      }
    },
    "staging": {
      "account_id": "234567890123",
      "role_name": "InventoryRole",
      "tags": {
        "Environment": "Staging",
        "Department": "Engineering"
      }
    }
  },
  "collection_settings": {
    "regions": ["us-east-1", "us-west-2", "eu-west-1"],
    "resource_types": ["ec2_instance", "rds_instance", "s3_bucket", "lambda_function"],
    "cost_thresholds": {
      "monthly_alert": 10000,
      "resource_alert": 500
    }
  }
}
EOF

# Step 8: Create terraform.tfvars.example
echo -e "\n${YELLOW}Step 8: Creating terraform.tfvars.example...${NC}"

cat > terraform/terraform.tfvars.example << 'EOF'
# AWS Configuration
aws_region = "us-east-1"
environment = "production"

# Stack Configuration
stack_name = "aws-inventory"

# DynamoDB Configuration
dynamodb_billing_mode = "PAY_PER_REQUEST"
# For PROVISIONED mode, uncomment these:
# dynamodb_billing_mode = "PROVISIONED"
# dynamodb_read_capacity = 10
# dynamodb_write_capacity = 10

# Lambda Configuration
lambda_timeout = 300
lambda_memory = 1024

# Schedule Configuration
schedule_expression = "rate(6 hours)"

# Alerts Configuration
notification_email = "your-email@example.com"
cost_alert_threshold = 10000

# Monitoring
enable_monitoring = true
log_retention_days = 30

# Security
external_id = "your-unique-external-id"

# Tags
tags = {
  Owner = "DevOps Team"
  Project = "AWS Inventory"
  CostCenter = "Engineering"
}
EOF

# Step 9: Create migration summary
echo -e "\n${YELLOW}Step 9: Creating migration summary...${NC}"

cat > MIGRATION_SUMMARY.md << 'EOF'
# Migration to Consolidated Version

## What Changed

### Infrastructure (Terraform)
- ✅ Migrated to modular Terraform structure
- ✅ Enhanced DynamoDB schema with pk/sk pattern
- ✅ Added department and timestamp indexes
- ✅ Integrated SNS notifications
- ✅ Added S3 bucket for reports
- ✅ CloudWatch dashboard and alarms

### Features (Enhanced)
- ✅ Cost analysis and optimization
- ✅ Security compliance monitoring
- ✅ Advanced query capabilities
- ✅ CSV export functionality
- ✅ Automated daily/weekly/monthly reports
- ✅ Real-time metrics and monitoring

### Code Structure
- `src/collector/enhanced_main.py` - Enhanced collector with RDS, S3, Lambda
- `src/query/enhanced_inventory_query.py` - Advanced query tool
- `src/lambda/enhanced_handler.py` - Multi-action Lambda handler
- `tests/unit/test_enhanced_collector.py` - Comprehensive tests

## Next Steps

1. **Review and update configuration**:
   ```bash
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   # Edit terraform.tfvars with your settings
   ```

2. **Deploy the infrastructure**:
   ```bash
   make deploy
   ```

3. **Deploy IAM roles in target accounts**:
   ```bash
   make deploy-iam
   ```

4. **Configure accounts**:
   ```bash
   cp config/accounts.json.example config/accounts.json
   # Edit with your AWS accounts
   ```

5. **Test the system**:
   ```bash
   make test
   make collect
   make query-cost
   ```

## Benefits of Consolidated Version

1. **Better Infrastructure Management**: Terraform provides better state management and modularity
2. **Enhanced Features**: Cost analysis, security monitoring, and advanced querying
3. **Improved Performance**: Parallel collection and optimized DynamoDB schema
4. **Comprehensive Monitoring**: CloudWatch dashboard, metrics, and alerts
5. **Automated Reporting**: Daily, weekly, and monthly reports to S3

## Rollback Plan

If you need to rollback:
1. Restore from backups in `backups/` directory
2. Run `terraform destroy` to remove new infrastructure
3. Redeploy previous version
EOF

echo -e "\n${GREEN}Migration preparation complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Review the changes in MIGRATION_SUMMARY.md"
echo "2. Copy and update terraform.tfvars:"
echo "   cp terraform/terraform.tfvars.example terraform/terraform.tfvars"
echo "3. Test the build process:"
echo "   make build-lambda"
echo "4. Deploy when ready:"
echo "   make deploy"
echo ""
echo "All original files have been backed up to: backups/$(date +%Y%m%d_*)"