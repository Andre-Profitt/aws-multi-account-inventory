variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for inventory storage"
  type        = string
  default     = "aws-inventory"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function for inventory collection"
  type        = string
  default     = "aws-inventory-collector"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 512
}

variable "schedule_expression" {
  description = "EventBridge schedule expression for inventory collection"
  type        = string
  default     = "rate(6 hours)"
}