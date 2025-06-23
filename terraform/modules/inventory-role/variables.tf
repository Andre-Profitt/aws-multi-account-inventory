variable "central_account_id" {
  description = "The AWS account ID of the central inventory account"
  type        = string
}

variable "role_name" {
  description = "Name of the IAM role for inventory collection"
  type        = string
  default     = "InventoryRole"
}