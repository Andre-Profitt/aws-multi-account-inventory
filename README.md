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

- **Multi-Account Support**: Collect inventory from unlimited AWS accounts
- **Automated Collection**: Scheduled via EventBridge (default: every 6 hours)
- **Resource Types Supported**:
  - EC2 Instances
  - RDS Databases
  - S3 Buckets
  - (Easily extensible for more resource types)
- **Secure Cross-Account Access**: Uses IAM role assumption with external ID
- **Serverless Architecture**: No infrastructure to manage
- **Cost Effective**: Typically < $15/month for most organizations

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

```bash
# Using Terraform
make deploy

# OR manually:
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
terraform init
terraform apply
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

```bash
# Query from DynamoDB
aws dynamodb scan \
  --table-name aws-inventory \
  --query 'Items[*].{Type:resource_type.S,ID:resource_id.S,Account:account_name.S}'
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

1. Add collection method to `src/collector/main.py`:
```python
def collect_new_resource(self, session, region, account_id, account_name):
    # Your collection logic here
    pass
```

2. Add the method call in `collect_account_inventory()`:
```python
futures.append(
    executor.submit(self.collect_new_resource, session, region, account_id, account_name)
)
```

3. Update IAM policies if needed for new permissions

4. Rebuild and deploy:
```bash
make build-lambda
make deploy
```

## Cost Optimization

Estimated monthly costs:
- Lambda: ~$0.20 (based on 6-hour schedule)
- DynamoDB: ~$5-10 (depending on data volume)
- CloudWatch Logs: ~$0.50

Total: **< $15/month** for most organizations

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

- Cross-account access uses role assumption with external ID
- Lambda function has minimal required permissions
- All data is encrypted at rest in DynamoDB
- No credentials are stored in code or configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details