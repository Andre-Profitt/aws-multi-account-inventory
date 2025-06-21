#!/bin/bash
set -e

case "$1" in
  iam)
    echo "Deploy IAM roles to each target account"
    ;;
  central)
    echo "Deploying DynamoDB table..."
    aws cloudformation deploy \
      --stack-name inventory-dynamodb \
      --template-file cloudformation/dynamodb-table.yaml
    ;;
  all)
    $0 central
    ;;
  *)
    echo "Usage: $0 [iam|central|all]"
    ;;
esac