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
