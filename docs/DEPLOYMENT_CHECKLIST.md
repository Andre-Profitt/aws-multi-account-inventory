# AWS Multi-Account Inventory Deployment Checklist

## Pre-Deployment

- [ ] **AWS CLI configured** with appropriate credentials
- [ ] **Terraform installed** (v1.0+) if using Terraform
- [ ] **Python 3.9+** installed
- [ ] **Central account ID** noted
- [ ] **Target account IDs** collected
- [ ] **Deployment method chosen**: Terraform or CloudFormation

## Phase 1: Target Account Setup

For **EACH** target account:

### Using Terraform:
```bash
cd terraform/target-account-role
terraform init
terraform apply -var="central_account_id=YOUR_CENTRAL_ACCOUNT_ID"
```

### Using CloudFormation:
```bash
aws cloudformation deploy \
  --stack-name inventory-role \
  --template-file cloudformation/iam-role.yaml \
  --parameter-overrides CentralAccountId=YOUR_CENTRAL_ACCOUNT_ID \
  --capabilities CAPABILITY_NAMED_IAM
```

- [ ] Engineering account role deployed
- [ ] Marketing account role deployed
- [ ] Production account role deployed
- [ ] _(Add more as needed)_

## Phase 2: Central Infrastructure

### Using Terraform:

1. **Configure variables**:
   ```bash
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   # Edit terraform.tfvars with your settings
   ```

2. **Build Lambda packages**:
   ```bash
   make build-lambda
   ```

3. **Deploy infrastructure**:
   ```bash
   make deploy
   # OR step by step:
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

### Using CloudFormation:

1. **Deploy DynamoDB**:
   ```bash
   ./scripts/deploy.sh central
   ```

2. **Build Lambda packages**:
   ```bash
   ./scripts/build-lambda.sh
   ```

3. **Deploy Lambda**:
   ```bash
   ./scripts/deploy.sh lambda
   ```

- [ ] DynamoDB table created
- [ ] Lambda function deployed
- [ ] EventBridge rule enabled
- [ ] CloudWatch log group created

## Phase 3: Configuration

1. **Create accounts configuration**:
   ```bash
   cp config/accounts.json.example config/accounts.json
   ```

2. **Edit config/accounts.json**:
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

3. **Update Lambda with config** (if needed):
   ```bash
   # Rebuild with updated config
   make build-lambda
   
   # Update Lambda function
   aws lambda update-function-code \
     --function-name aws-inventory-collector \
     --zip-file fileb://lambda-deployment.zip
   ```

- [ ] accounts.json configured
- [ ] All account IDs verified
- [ ] Lambda function updated

## Phase 4: Testing

1. **Test Lambda manually**:
   ```bash
   aws lambda invoke \
     --function-name aws-inventory-collector \
     --payload '{}' \
     output.json
   
   cat output.json
   ```

2. **Check CloudWatch logs**:
   ```bash
   aws logs tail /aws/lambda/aws-inventory-collector --follow
   ```

3. **Verify DynamoDB data**:
   ```bash
   aws dynamodb scan \
     --table-name aws-inventory \
     --limit 5
   ```

4. **Test local collection**:
   ```bash
   make collect
   ```

5. **Query inventory**:
   ```bash
   make query
   ```

- [ ] Lambda executes successfully
- [ ] No permission errors in logs
- [ ] Data appears in DynamoDB
- [ ] Query tool returns results

## Phase 5: Monitoring Setup

1. **Create CloudWatch alarm** for Lambda errors:
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name inventory-collector-errors \
     --alarm-description "Alert on Lambda errors" \
     --metric-name Errors \
     --namespace AWS/Lambda \
     --statistic Sum \
     --period 3600 \
     --threshold 1 \
     --comparison-operator GreaterThanThreshold \
     --dimensions Name=FunctionName,Value=aws-inventory-collector \
     --evaluation-periods 1
   ```

2. **Set up SNS notifications** (optional)

- [ ] CloudWatch alarms configured
- [ ] SNS topic created (if using)
- [ ] Alert recipients added

## Post-Deployment Verification

- [ ] EventBridge rule is enabled
- [ ] Lambda has correct environment variables
- [ ] Lambda timeout is sufficient (300s recommended)
- [ ] DynamoDB has proper capacity
- [ ] All target accounts accessible
- [ ] First scheduled run successful

## Troubleshooting Commands

```bash
# Check Lambda function status
aws lambda get-function --function-name aws-inventory-collector

# Check EventBridge rule
aws events describe-rule --name aws-inventory-collector-schedule

# Check recent Lambda executions
aws logs tail /aws/lambda/aws-inventory-collector --since 1h

# Test role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::TARGET_ACCOUNT_ID:role/InventoryRole \
  --role-session-name test-session

# Force immediate collection
aws events put-events \
  --entries '[{"Source":"manual","DetailType":"trigger","Detail":"{}"}]'
```

## Rollback Plan

If issues occur:

1. **Disable EventBridge rule**:
   ```bash
   aws events disable-rule --name aws-inventory-collector-schedule
   ```

2. **Investigate logs**:
   ```bash
   aws logs tail /aws/lambda/aws-inventory-collector --since 1h
   ```

3. **Rollback if needed**:
   ```bash
   # Terraform
   cd terraform && terraform destroy
   
   # CloudFormation
   aws cloudformation delete-stack --stack-name inventory-lambda
   aws cloudformation delete-stack --stack-name inventory-dynamodb
   ```

## Success Criteria

✅ All target account roles deployed  
✅ Central infrastructure operational  
✅ Lambda executing on schedule  
✅ Inventory data populating in DynamoDB  
✅ No errors in CloudWatch logs  
✅ Query tool returning accurate results

---

**Estimated Time**: 30-45 minutes for complete deployment  
**Support**: Create an issue at https://github.com/andre-profitt/aws-multi-account-inventory