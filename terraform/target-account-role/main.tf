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

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "central_account_id" {
  description = "AWS Account ID of the central account where Lambda runs"
  type        = string
}

variable "role_name" {
  description = "Name of the inventory collection role"
  type        = string
  default     = "InventoryRole"
}

# IAM Role for inventory collection
resource "aws_iam_role" "inventory_role" {
  name = var.role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.central_account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "inventory-collector"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "Inventory Collection Role"
    Purpose     = "Allow central account to collect resource inventory"
    CentralAccount = var.central_account_id
  }
}

# IAM Policy for read-only access
resource "aws_iam_role_policy" "inventory_readonly" {
  name = "InventoryReadOnlyPolicy"
  role = aws_iam_role.inventory_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          # EC2
          "ec2:Describe*",
          "ec2:List*",
          "ec2:Get*",
          
          # RDS
          "rds:Describe*",
          "rds:List*",
          
          # S3
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation",
          "s3:GetBucketTagging",
          "s3:GetBucketPolicy",
          "s3:GetBucketVersioning",
          "s3:GetLifecycleConfiguration",
          "s3:GetBucketLogging",
          "s3:GetBucketWebsite",
          "s3:GetBucketNotification",
          "s3:GetAccelerateConfiguration",
          "s3:GetBucketRequestPayment",
          "s3:GetBucketCors",
          "s3:GetBucketAcl",
          "s3:ListBucket",
          
          # ELB
          "elasticloadbalancing:Describe*",
          
          # Lambda
          "lambda:List*",
          "lambda:Get*",
          
          # DynamoDB
          "dynamodb:ListTables",
          "dynamodb:DescribeTable",
          "dynamodb:ListTagsOfResource",
          
          # CloudFormation
          "cloudformation:ListStacks",
          "cloudformation:DescribeStacks",
          "cloudformation:ListStackResources",
          
          # CloudWatch
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          
          # Cost Explorer
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetReservationUtilization",
          "ce:GetSavingsPlansPurchaseRecommendation",
          
          # Organizations (if applicable)
          "organizations:ListAccounts",
          "organizations:DescribeAccount",
          
          # Tag Editor
          "tag:GetResources",
          "tag:GetTagKeys",
          "tag:GetTagValues",
          
          # General
          "iam:ListInstanceProfiles",
          "iam:ListRoles",
          "autoscaling:Describe*",
          "sns:List*",
          "sqs:List*"
        ]
        Resource = "*"
      }
    ]
  })
}

output "role_arn" {
  description = "ARN of the inventory collection role"
  value       = aws_iam_role.inventory_role.arn
}

output "role_name" {
  description = "Name of the inventory collection role"
  value       = aws_iam_role.inventory_role.name
}