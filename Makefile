.PHONY: help install test deploy deploy-plan deploy-iam collect query clean validate build-lambda

help:
	@echo "AWS Multi-Account Inventory"
	@echo "make install       - Install dependencies"
	@echo "make validate      - Validate Terraform configuration"
	@echo "make build-lambda  - Build Lambda deployment package"
	@echo "make deploy-plan   - Show Terraform deployment plan"
	@echo "make deploy        - Deploy infrastructure with Terraform"
	@echo "make deploy-iam    - Show IAM role deployment instructions"
	@echo "make collect       - Run inventory collection locally"
	@echo "make query         - Query inventory"
	@echo "make clean         - Clean up generated files"

install:
	pip install -r requirements.txt
	@echo "Checking Terraform installation..."
	@terraform version || echo "Please install Terraform: https://www.terraform.io/downloads"

validate:
	cd terraform && terraform init && terraform validate

build-lambda:
	@echo "Building Lambda deployment package..."
	@chmod +x scripts/build-lambda.sh
	@./scripts/build-lambda.sh

deploy-plan: build-lambda
	cd terraform && terraform init && terraform plan

deploy: build-lambda
	./scripts/deploy-terraform.sh all

deploy-iam:
	@echo "To deploy IAM roles in target accounts:"
	@echo "1. cd terraform/target-account-role"
	@echo "2. terraform init"
	@echo "3. terraform apply -var=\"central_account_id=YOUR_CENTRAL_ACCOUNT_ID\""

collect:
	python src/collector/main.py --config config/accounts.json

query:
	python src/query/inventory_query.py --action summary

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf lambda-build/
	rm -f lambda-deployment.zip
	rm -f lambda-layer.zip