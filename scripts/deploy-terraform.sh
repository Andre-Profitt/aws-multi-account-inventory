#!/bin/bash

# Terraform deployment script for AWS Multi-Account Inventory
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check if Terraform is installed
check_terraform() {
    if ! command -v terraform &> /dev/null; then
        print_message "$RED" "Error: Terraform is not installed."
        print_message "$YELLOW" "Please install Terraform from: https://www.terraform.io/downloads"
        exit 1
    fi
    print_message "$GREEN" "✓ Terraform is installed: $(terraform version -json | jq -r '.terraform_version')"
}

# Build Lambda packages
build_lambda() {
    print_message "$YELLOW" "Building Lambda deployment packages..."
    if [ -f "scripts/build-lambda.sh" ]; then
        chmod +x scripts/build-lambda.sh
        ./scripts/build-lambda.sh
    else
        print_message "$RED" "Error: scripts/build-lambda.sh not found"
        exit 1
    fi
}

# Initialize Terraform
init_terraform() {
    print_message "$YELLOW" "Initializing Terraform..."
    cd terraform
    terraform init
    print_message "$GREEN" "✓ Terraform initialized successfully"
}

# Validate Terraform configuration
validate_terraform() {
    print_message "$YELLOW" "Validating Terraform configuration..."
    terraform validate
    print_message "$GREEN" "✓ Terraform configuration is valid"
}

# Plan Terraform deployment
plan_terraform() {
    print_message "$YELLOW" "Planning Terraform deployment..."
    terraform plan -out=tfplan
    print_message "$GREEN" "✓ Terraform plan created successfully"
}

# Apply Terraform deployment
apply_terraform() {
    print_message "$YELLOW" "Applying Terraform deployment..."
    terraform apply tfplan
    print_message "$GREEN" "✓ Terraform deployment completed successfully"
}

# Show deployment outputs
show_outputs() {
    print_message "$YELLOW" "Deployment outputs:"
    terraform output -json | jq '.'
}

# Main deployment function
deploy_all() {
    check_terraform
    build_lambda
    init_terraform
    validate_terraform
    plan_terraform
    
    # Ask for confirmation
    print_message "$YELLOW" "Do you want to apply these changes? (yes/no)"
    read -r confirmation
    
    if [[ "$confirmation" == "yes" ]]; then
        apply_terraform
        show_outputs
        
        print_message "$GREEN" "✅ Deployment complete!"
        print_message "$YELLOW" "Next steps:"
        print_message "$YELLOW" "1. Configure accounts in config/accounts.json"
        print_message "$YELLOW" "2. Deploy IAM roles to target accounts"
        print_message "$YELLOW" "3. Test Lambda function: aws lambda invoke --function-name aws-inventory-collector output.json"
    else
        print_message "$RED" "Deployment cancelled."
        exit 0
    fi
}

# Show usage
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  all      - Run full deployment (build, init, validate, plan, apply)"
    echo "  build    - Build Lambda deployment packages"
    echo "  init     - Initialize Terraform"
    echo "  validate - Validate Terraform configuration"
    echo "  plan     - Create deployment plan"
    echo "  apply    - Apply deployment"
    echo "  outputs  - Show deployment outputs"
    echo "  help     - Show this help message"
}

# Main script logic
case "${1:-help}" in
    all)
        deploy_all
        ;;
    build)
        build_lambda
        ;;
    init)
        check_terraform
        init_terraform
        ;;
    validate)
        check_terraform
        init_terraform
        validate_terraform
        ;;
    plan)
        check_terraform
        build_lambda
        init_terraform
        validate_terraform
        plan_terraform
        ;;
    apply)
        check_terraform
        apply_terraform
        show_outputs
        ;;
    outputs)
        cd terraform
        show_outputs
        ;;
    help|*)
        usage
        ;;
esac