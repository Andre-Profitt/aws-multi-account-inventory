terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
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

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "aws-inventory-collector"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory" {
  description = "Lambda memory in MB"
  type        = number
  default     = 512
}

variable "schedule_expression" {
  description = "EventBridge schedule expression"
  type        = string
  default     = "rate(6 hours)"
}

# DynamoDB Table
resource "aws_dynamodb_table" "inventory" {
  name         = "aws-inventory"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "composite_key"
  range_key    = "timestamp"

  attribute {
    name = "composite_key"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "account_id"
    type = "S"
  }

  attribute {
    name = "resource_type"
    type = "S"
  }

  global_secondary_index {
    name            = "account-resource-index"
    hash_key        = "account_id"
    range_key       = "resource_type"
    projection_type = "ALL"
  }

  tags = {
    Name        = "AWS Inventory Table"
    Environment = var.environment
    Project     = "aws-multi-account-inventory"
  }
}

# Lambda Execution Role
resource "aws_iam_role" "lambda_execution" {
  name = "${var.lambda_function_name}-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "Lambda Execution Role"
    Environment = var.environment
    Project     = "aws-multi-account-inventory"
  }
}

# Lambda Execution Role Policy
resource "aws_iam_role_policy" "lambda_execution_policy" {
  name = "${var.lambda_function_name}-execution-policy"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.inventory.arn,
          "${aws_dynamodb_table.inventory.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sts:AssumeRole"
        ]
        Resource = "arn:aws:iam::*:role/InventoryRole"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeRegions"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda basic execution policy attachment
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 bucket for Lambda deployment packages
resource "aws_s3_bucket" "lambda_deployment" {
  bucket = "${var.lambda_function_name}-deployment-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "Lambda Deployment Bucket"
    Environment = var.environment
    Project     = "aws-multi-account-inventory"
  }
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "lambda_deployment" {
  bucket = aws_s3_bucket.lambda_deployment.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Lambda Layer for dependencies
resource "aws_lambda_layer_version" "dependencies" {
  filename            = "../lambda-layer.zip"
  layer_name          = "${var.lambda_function_name}-dependencies"
  compatible_runtimes = ["python3.9", "python3.10", "python3.11"]
  description         = "Dependencies for AWS inventory collector"

  lifecycle {
    ignore_changes = [filename]
  }
}

# Lambda Function
resource "aws_lambda_function" "inventory_collector" {
  function_name = var.lambda_function_name
  role          = aws_iam_role.lambda_execution.arn
  
  filename         = "../lambda-deployment.zip"
  source_code_hash = filebase64sha256("../lambda-deployment.zip")
  
  handler = "src.lambda.handler.lambda_handler"
  runtime = "python3.9"
  timeout = var.lambda_timeout
  memory_size = var.lambda_memory
  
  layers = [aws_lambda_layer_version.dependencies.arn]
  
  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.inventory.name
      AWS_DEFAULT_REGION  = var.aws_region
    }
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }

  tags = {
    Name        = "Inventory Collector Lambda"
    Environment = var.environment
    Project     = "aws-multi-account-inventory"
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14

  tags = {
    Name        = "Lambda Logs"
    Environment = var.environment
    Project     = "aws-multi-account-inventory"
  }
}

# EventBridge Rule for scheduling
resource "aws_cloudwatch_event_rule" "inventory_schedule" {
  name                = "${var.lambda_function_name}-schedule"
  description         = "Trigger inventory collection"
  schedule_expression = var.schedule_expression

  tags = {
    Name        = "Inventory Collection Schedule"
    Environment = var.environment
    Project     = "aws-multi-account-inventory"
  }
}

# EventBridge Target
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.inventory_schedule.name
  target_id = "LambdaTarget"
  arn       = aws_lambda_function.inventory_collector.arn
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.inventory_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.inventory_schedule.arn
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}