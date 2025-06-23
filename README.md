# AWS Multi-Account Inventory System

A serverless solution for collecting and managing AWS resource inventory across multiple accounts.

## Overview

This system automatically discovers and catalogs AWS resources across multiple accounts, storing the inventory in a centralized DynamoDB table. It's designed for organizations managing multiple AWS accounts who need visibility into their resource usage.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐
│   EventBridge   │────▶│    Lambda    │────▶│   DynamoDB    │
│  (every 6 hrs)  │     │   Function   │     │    Table      │
└─────────────────┘     └──────┬───────┘     └───────────────┘
                               │
                               │ Assumes Role
                               ▼
                      ┌─────────────────┐
                      │  Target Account │
                      │  InventoryRole  │
                      └─────────────────┘
```

## Features

### Core Features
- **Multi-Account Support**: Collect inventory from unlimited AWS accounts
- **Automated Collection**: Scheduled via EventBridge (configurable, default: every 6 hours)
- **Resource Types Supported**:
  - EC2 Instances (with state, type, and utilization tracking)
  - RDS Databases and Clusters (with encryption status)
  - S3 Buckets (with size, encryption, and public access status)
  - Lambda Functions (with invocation metrics and error rates)
- **Secure Cross-Account Access**: Uses IAM role assumption with external ID
- **Serverless Architecture**: No infrastructure to manage
- **Cost Effective**: Typically < $15/month for most organizations

### Enhanced Features
- **Cost Analysis & Optimization**:
  - Real-time cost estimation for all resources
  - Daily cost analysis reports
  - Identification of idle and oversized resources
  - Monthly cost projections and alerts
- **Security Compliance**:
  - Weekly security checks
  - Detection of unencrypted resources
  - Public access monitoring for S3 buckets
  - Automated compliance alerts
- **Advanced Querying**:
  - Filter by account, region, resource type, or tags
  - Export to CSV for external analysis
  - Department and cost center reporting
  - Stale resource identification
- **Monitoring & Alerts**:
  - CloudWatch dashboard with key metrics
  - SNS notifications for cost thresholds
  - Error tracking and alerting
  - Collection performance metrics
- **Automated Reporting**:
  - Daily cost reports
  - Weekly security summaries
  - Monthly optimization recommendations
  - All reports saved to S3

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform 1.0+ or AWS CloudFormation
- Python 3.9+
- Central AWS account for deployment

### 1. Clone and Setup

```bash
git clone <repository-url>
cd aws-multi-account-inventory
pip install -r requirements.txt
```

### 2. Configure Accounts

Copy the example configuration and update with your accounts:

```bash
cp config/accounts.json.example config/accounts.json
```

Edit `config/accounts.json`:
```json
{
  "accounts": {
    "engineering": {
      "account_id": "123456789012",
      "role_name": "InventoryRole"
    },
    "marketing": {
      "account_id": "234567890123",
      "role_name": "InventoryRole"
    }
  }
}
```

### 3. Deploy IAM Roles in Target Accounts

For each target account, deploy the inventory collection role:

```bash
cd terraform/target-account-role
terraform init
terraform apply -var="central_account_id=YOUR_CENTRAL_ACCOUNT_ID"
```

### 4. Deploy Central Infrastructure

You can deploy using either Terraform or CloudFormation:

#### Using Terraform (Recommended)
```bash
# Using make
make deploy

# OR manually:
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
terraform init
terraform apply
```

#### Using CloudFormation
```bash
# Deploy all infrastructure
./scripts/deploy.sh all

# OR deploy components separately:
./scripts/deploy.sh central  # DynamoDB table
./scripts/deploy.sh lambda   # Lambda function
```

### 5. Test the Deployment

```bash
# Invoke Lambda manually
aws lambda invoke \
  --function-name aws-inventory-collector \
  --payload '{}' \
  output.json

# Check the output
cat output.json

# View CloudWatch logs
aws logs tail /aws/lambda/aws-inventory-collector --follow
```

## Usage

### Manual Collection

Run inventory collection locally:
```bash
make collect
```

### Query Inventory

The project includes an enhanced query tool with cost analysis and advanced filtering:

```bash
# Show inventory summary with costs
python -m src.query.enhanced_inventory_query --action summary

# Perform cost analysis with optimization recommendations
python -m src.query.enhanced_inventory_query --action cost

# Security compliance check
python -m src.query.enhanced_inventory_query --action security

# Find stale resources (default: 90 days)
python -m src.query.enhanced_inventory_query --action stale --days 60

# Export to CSV with filters
python -m src.query.enhanced_inventory_query --action export \
  --department engineering \
  --environment production \
  --output engineering-prod.csv

# Get resources by account
python -m src.query.enhanced_inventory_query --action by-account \
  --account-name production

# Filter by multiple criteria
python -m src.query.enhanced_inventory_query --action by-type \
  --resource-type ec2_instance \
  --region us-east-1 \
  --days 7

# Get details for a specific resource
python -m src.query.enhanced_inventory_query --action details \
  --resource-id i-0123456789abcdef
```

### Update Lambda Function

After making code changes:
```bash
make build-lambda
aws lambda update-function-code \
  --function-name aws-inventory-collector \
  --zip-file fileb://lambda-deployment.zip
```

## Configuration

### Terraform Variables

Key variables in `terraform.tfvars`:

```hcl
aws_region           = "us-east-1"
lambda_timeout       = 300        # 5 minutes
lambda_memory        = 512        # MB
schedule_expression  = "rate(6 hours)"
```

### Schedule Expressions

Examples:
- `rate(6 hours)` - Every 6 hours
- `rate(1 day)` - Daily
- `cron(0 12 * * ? *)` - Every day at 12:00 PM UTC

## Extending the Collector

To add new resource types:

1. Add collection method to `src/collector/enhanced_main.py`:
```python
def collect_new_resource(self, session, region, account_id, account_name):
    resources = []
    try:
        client = session.client('service-name', region_name=region)
        # Collection logic with pagination
        paginator = client.get_paginator('describe_resources')
        for page in paginator.paginate():
            for resource in page['Resources']:
                resources.append({
                    'resource_type': 'new_resource',
                    'resource_id': resource['Id'],
                    'account_id': account_id,
                    'account_name': account_name,
                    'region': region,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'attributes': {
                        # Resource-specific attributes
                    },
                    'estimated_monthly_cost': self.estimate_cost(resource)
                })
    except Exception as e:
        logger.error(f"Error collecting new resources: {e}")
    return resources
```

2. Add cost estimation method:
```python
def estimate_new_resource_cost(self, resource):
    # Add pricing logic
    return monthly_cost
```

3. Add the method call in `collect_account_inventory()`:
```python
futures.append(
    executor.submit(self.collect_new_resource, session, region, account_id, account_name)
)
```

4. Update IAM policies in CloudFormation template

5. Add unit tests in `tests/unit/test_enhanced_collector.py`

6. Rebuild and deploy:
```bash
make build-lambda
make deploy
```

## Cost Optimization

### Estimated Monthly Costs
- Lambda Execution: ~$1-2 (includes all scheduled functions)
- DynamoDB: ~$5-10 (depending on data volume)
- CloudWatch Logs: ~$1-2
- CloudWatch Metrics & Alarms: ~$1
- S3 Reports Storage: ~$0.50
- SNS Notifications: ~$0.10

Total: **< $15-20/month** for most organizations

### Built-in Cost Optimization Features

1. **Automated Cost Analysis**:
   - Daily cost reports with trends
   - Identification of top expensive resources
   - Monthly cost projections

2. **Resource Optimization Recommendations**:
   - **Idle Resources**: EC2 instances stopped >30 days, unused Lambda functions
   - **Oversized Resources**: Large instance types with low utilization
   - **Stale Resources**: Empty S3 buckets, unused resources >90 days

3. **Cost Alerts**:
   - Configurable thresholds (default: $10,000/month)
   - Per-resource cost tracking
   - Department/cost center allocation

4. **Example Savings Opportunities**:
   ```bash
   # View all optimization opportunities
   python -m src.query.enhanced_inventory_query --action cost
   
   # Find idle resources
   python -m src.query.enhanced_inventory_query --action stale --days 30
   
   # Export high-cost resources
   python -m src.query.enhanced_inventory_query --action export \
     --output high-cost-resources.csv
   ```

## Troubleshooting

### Lambda Timeout
- Increase `lambda_timeout` in terraform.tfvars
- Consider collecting fewer regions or resource types per run

### Permission Errors
```bash
# Test role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::TARGET_ACCOUNT:role/InventoryRole \
  --role-session-name test-session \
  --external-id inventory-collector
```

### Missing Resources
- Check Lambda has permissions for the resource type
- Verify the target account role has necessary read permissions
- Check CloudWatch logs for specific errors

## Security

### Security Features

1. **Access Control**:
   - Cross-account access uses role assumption with external ID
   - Lambda function has minimal required permissions
   - All API calls are logged to CloudTrail

2. **Data Protection**:
   - All data encrypted at rest in DynamoDB
   - S3 buckets use AES-256 encryption
   - Reports bucket has versioning enabled
   - No credentials stored in code or configuration

3. **Compliance Monitoring**:
   - **Weekly Security Checks**:
     - Unencrypted RDS instances
     - Unencrypted S3 buckets
     - Public S3 buckets
     - Missing security group rules
   
   - **Automated Alerts**:
     ```bash
     # Run security check manually
     python -m src.query.enhanced_inventory_query --action security
     ```

4. **Network Security**:
   - VPC endpoints for DynamoDB access (optional)
   - No inbound network access required
   - All traffic over HTTPS/TLS

### Security Best Practices

1. **IAM Role Configuration**:
   - Use unique external IDs per environment
   - Regularly rotate external IDs
   - Audit role trust policies

2. **Data Handling**:
   - Enable DynamoDB point-in-time recovery
   - Set appropriate S3 lifecycle policies
   - Regular backup of configuration

3. **Monitoring**:
   - Enable CloudTrail for audit logging
   - Set up GuardDuty for threat detection
   - Regular review of access patterns

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details