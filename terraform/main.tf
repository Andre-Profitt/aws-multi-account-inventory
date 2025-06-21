terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Configure your backend settings
    # bucket = "your-terraform-state-bucket"
    # key    = "aws-inventory/terraform.tfstate"
    # region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# DynamoDB Table for inventory storage
resource "aws_dynamodb_table" "inventory" {
  name           = var.dynamodb_table_name
  billing_mode   = "PROVISIONED"
  read_capacity  = 10
  write_capacity = 10
  
  hash_key  = "pk"
  range_key = "sk"
  
  attribute {
    name = "pk"
    type = "S"
  }
  
  attribute {
    name = "sk"
    type = "S"
  }
  
  attribute {
    name = "resource_type"
    type = "S"
  }
  
  attribute {
    name = "department"
    type = "S"
  }
  
  global_secondary_index {
    name            = "resource-type-index"
    hash_key        = "resource_type"
    range_key       = "sk"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"
  }
  
  global_secondary_index {
    name            = "department-index"
    hash_key        = "department"
    range_key       = "sk"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "ALL"
  }
  
  tags = {
    Name        = "AWS Inventory Table"
    Environment = var.environment
    Project     = "aws-multi-account-inventory"
  }
}