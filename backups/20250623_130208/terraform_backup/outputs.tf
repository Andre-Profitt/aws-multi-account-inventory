<<<<<<< HEAD
output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.inventory_collector.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.inventory_collector.arn
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
=======
output "dynamodb_table_name" {
  description = "Name of the DynamoDB inventory table"
>>>>>>> origin/main
  value       = aws_dynamodb_table.inventory.name
}

output "dynamodb_table_arn" {
<<<<<<< HEAD
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.inventory.arn
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for Lambda deployments"
  value       = aws_s3_bucket.lambda_deployment.id
}

output "schedule_rule_name" {
  description = "Name of the EventBridge schedule rule"
  value       = aws_cloudwatch_event_rule.inventory_schedule.name
}

output "log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda_logs.name
=======
  description = "ARN of the DynamoDB inventory table"
  value       = aws_dynamodb_table.inventory.arn
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
>>>>>>> origin/main
}