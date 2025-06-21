# Terraform configuration for deploying inventory role in target accounts
# This should be run in each target account

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "central_account_id" {
  description = "Central inventory account ID"
  type        = string
}

variable "role_name" {
  description = "Name of the inventory role"
  type        = string
  default     = "InventoryRole"
}

provider "aws" {
  # Will use the credentials of the target account
}

module "inventory_role" {
  source = "../modules/inventory-role"
  
  central_account_id = var.central_account_id
  role_name         = var.role_name
}

output "role_arn" {
  description = "ARN of the created inventory role"
  value       = module.inventory_role.role_arn
}

output "instructions" {
  description = "Next steps"
  value       = <<-EOT
    Role created successfully!
    
    Add this account to your accounts.json configuration:
    {
      "department_name": {
        "account_id": "${data.aws_caller_identity.current.account_id}",
        "role_name": "${module.inventory_role.role_name}"
      }
    }
  EOT
}

data "aws_caller_identity" "current" {}