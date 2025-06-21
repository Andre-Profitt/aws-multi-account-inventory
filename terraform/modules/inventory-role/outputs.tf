output "role_arn" {
  description = "ARN of the inventory collection role"
  value       = aws_iam_role.inventory_role.arn
}

output "role_name" {
  description = "Name of the inventory collection role"
  value       = aws_iam_role.inventory_role.name
}