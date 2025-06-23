#!/bin/bash
set -e

case "$1" in
  iam)
    echo "Deploy IAM roles to each target account"
    echo "Run in each target account:"
    echo "  aws cloudformation deploy \\"
    echo "    --stack-name inventory-role \\"
    echo "    --template-file cloudformation/iam-role.yaml \\"
    echo "    --parameter-overrides CentralAccountId=YOUR_CENTRAL_ACCOUNT_ID \\"
    echo "    --capabilities CAPABILITY_NAMED_IAM"
    ;;
  central)
    echo "Deploying DynamoDB table..."
    aws cloudformation deploy \
      --stack-name inventory-dynamodb \
      --template-file cloudformation/dynamodb-table.yaml
    ;;
  lambda)
    echo "Building Lambda deployment package..."
    ./scripts/build-lambda.sh
    
    echo "Deploying Lambda function..."
    aws cloudformation deploy \
      --stack-name inventory-lambda \
      --template-file cloudformation/lambda-collector.yaml \
      --capabilities CAPABILITY_IAM
    
    echo "Updating Lambda function code..."
    FUNCTION_NAME=$(aws cloudformation describe-stacks \
      --stack-name inventory-lambda \
      --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
      --output text)
    
    aws lambda update-function-code \
      --function-name "$FUNCTION_NAME" \
      --zip-file fileb://lambda-deployment.zip
    ;;
  all)
    $0 central
    $0 lambda
    echo ""
    echo "✅ Central infrastructure deployed!"
    echo ""
    echo "Next steps:"
    echo "1. Deploy IAM roles in each target account (run: $0 iam)"
    echo "2. Update config/accounts.json with your AWS accounts"
    echo "3. Test Lambda function:"
    echo "   aws lambda invoke --function-name inventory-lambda-collector output.json"
    ;;
  *)
    echo "Usage: $0 [iam|central|lambda|all]"
    echo ""
    echo "Commands:"
    echo "  iam     - Show instructions for IAM role deployment"
    echo "  central - Deploy DynamoDB table"
    echo "  lambda  - Deploy Lambda function"
    echo "  all     - Deploy all central infrastructure"
    ;;
esac