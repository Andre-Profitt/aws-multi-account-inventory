output "dynamodb_table_name" {
  description = "Name of the DynamoDB inventory table"
  value       = aws_dynamodb_table.inventory.name
}

output "dynamodb_table_arn" {
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
}