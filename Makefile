.PHONY: help install test deploy deploy-plan deploy-iam collect query clean validate build-lambda

help:
	@echo "AWS Multi-Account Inventory - Enhanced Edition"
	@echo "make install       - Install dependencies"
	@echo "make validate      - Validate Terraform configuration"
	@echo "make build-lambda  - Build Lambda deployment package"
	@echo "make deploy-plan   - Show Terraform deployment plan"
	@echo "make deploy        - Deploy infrastructure with Terraform"
	@echo "make deploy-iam    - Deploy IAM roles in target accounts"
	@echo "make collect       - Run inventory collection locally"
	@echo "make query         - Query inventory summary"
	@echo "make query-cost    - Run cost analysis"
	@echo "make query-security - Check security compliance"
	@echo "make test          - Run unit tests"
	@echo "make clean         - Clean up generated files"

install:
	pip install -r requirements.txt
	pip install pandas tabulate pytest moto
	@echo "Checking Terraform installation..."
	@terraform version || echo "Please install Terraform: https://www.terraform.io/downloads"

validate:
	cd terraform && terraform init && terraform validate

build-lambda:
	@echo "Building Lambda deployment packages..."
	@chmod +x scripts/build-lambda-enhanced.sh
	@./scripts/build-lambda-enhanced.sh

deploy-plan: build-lambda
	cd terraform && terraform init && terraform plan

deploy: build-lambda
	cd terraform && terraform init && terraform apply

deploy-iam:
	@echo "To deploy IAM roles in target accounts:"
	@echo "1. cd terraform/target-account-role"
	@echo "2. terraform init"
	@echo "3. terraform apply -var=\"central_account_id=YOUR_CENTRAL_ACCOUNT_ID\""

collect:
	python src/collector/enhanced_main.py --config config/accounts.json

query:
	python -m src.query.enhanced_inventory_query --action summary

query-cost:
	python -m src.query.enhanced_inventory_query --action cost

query-security:
	python -m src.query.enhanced_inventory_query --action security

query-export:
	python -m src.query.enhanced_inventory_query --action export --output inventory-export.csv

test:
	python -m pytest tests/unit/test_enhanced_collector.py -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf lambda-build/
	rm -f lambda-deployment.zip
	rm -f lambda-layer.zip
