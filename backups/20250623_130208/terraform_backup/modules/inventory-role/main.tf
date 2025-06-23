# IAM role for inventory collection in target accounts
resource "aws_iam_role" "inventory_role" {
  name = var.role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.central_account_id}:root"
        }
      }
    ]
  })

  tags = {
    Name        = "Inventory Collection Role"
    Project     = "aws-multi-account-inventory"
    ManagedBy   = "Terraform"
  }
}

# Policy for inventory collection
resource "aws_iam_role_policy" "inventory_policy" {
  name = "InventoryCollectionPolicy"
  role = aws_iam_role.inventory_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "rds:Describe*",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
          "s3:GetBucketEncryption",
          "s3:GetBucketTagging",
          "lambda:List*",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "iam:ListUsers",
          "iam:ListRoles",
          "iam:ListGroups",
          "iam:ListPolicies",
          "iam:GetUser",
          "iam:GetRole",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "tag:GetResources",
          "tag:GetTagKeys",
          "tag:GetTagValues"
        ]
        Resource = "*"
      }
    ]
  })
}