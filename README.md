# aws-multi-account-inventory

A comprehensive AWS resource inventory system that collects and tracks resources across multiple AWS accounts, departments, and regions.

## Features

- Multi-Account Support
- EC2, RDS, S3, Lambda inventory collection
- DynamoDB storage with efficient querying
- Lambda-based automated collection
- Cost optimization insights

## Quick Start

```bash
# Configure accounts
cp config/accounts.json.example config/accounts.json
# Edit with your account IDs

# Deploy IAM roles (in each target account)
aws cloudformation create-stack \
  --stack-name inventory-role \
  --template-body file://cloudformation/iam-role.yaml \
  --parameters ParameterKey=CentralAccountId,ParameterValue=YOUR_ACCOUNT_ID \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy central infrastructure
./scripts/deploy.sh central

# Run collection
python src/collector/main.py --config config/accounts.json
```

## Repository: https://github.com/andre-profitt/aws-multi-account-inventory