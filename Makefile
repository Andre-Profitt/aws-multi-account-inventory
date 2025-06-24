.PHONY: help install test deploy deploy-plan deploy-iam collect query clean validate build-lambda
.PHONY: install-dev lint security audit docs pre-commit-all aws-lambda-tune aws-cost-analyze aws-full-audit

help:
	@echo "AWS Multi-Account Inventory - Enhanced Edition"
	@echo ""
	@echo "Deployment Commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make validate      - Validate Terraform configuration"
	@echo "  make build-lambda  - Build Lambda deployment package"
	@echo "  make deploy-plan   - Show Terraform deployment plan"
	@echo "  make deploy        - Deploy infrastructure with Terraform"
	@echo "  make deploy-iam    - Deploy IAM roles in target accounts"
	@echo ""
	@echo "Operational Commands:"
	@echo "  make collect       - Run inventory collection locally"
	@echo "  make query         - Query inventory summary"
	@echo "  make query-cost    - Run cost analysis"
	@echo "  make query-security - Check security compliance"
	@echo ""
	@echo "Development & Quality Commands:"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make test          - Run unit tests"
	@echo "  make lint          - Run linting checks"
	@echo "  make security      - Run security scans"
	@echo "  make audit         - Run full audit suite"
	@echo "  make docs          - Check documentation"
	@echo "  make clean         - Clean up generated files"
	@echo ""
	@echo "AWS Analysis Commands:"
	@echo "  make aws-lambda-tune - Analyze Lambda performance"
	@echo "  make aws-cost-analyze - Analyze AWS costs"
	@echo "  make aws-full-audit  - Run complete AWS audit"

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
	python -m src.query.inventory_query --action summary

query-cost:
	python -m src.query.inventory_query --action cost

query-security:
	python -m src.query.inventory_query --action security

query-export:
	python -m src.query.inventory_query --action export --output inventory-export.csv

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
	rm -rf audit/reports/*
	rm -rf .ruff_cache/

# Development and Quality Commands
install-dev: install
	pip install -r requirements-dev.txt
	pre-commit install

lint:
	@echo "Running Ruff linter..."
	ruff check .
	@echo "Running Ruff formatter..."
	ruff format --check .
	@echo "Checking for dead code..."
	vulture . --min-confidence 80

security:
	@echo "Running Bandit security scan..."
	bandit -r . -f json -o audit/reports/bandit-report.json
	@echo "Running Safety dependency check..."
	safety check --json --output audit/reports/safety-report.json
	@echo "Scanning for secrets..."
	detect-secrets scan --baseline .secrets.baseline

infrastructure:
	@echo "Scanning CloudFormation templates..."
	cfn_nag_scan --input-path cloudformation/ --output-format json || true
	@echo "Scanning Terraform files..."
	tfsec . --format json --out audit/reports/tfsec-report.json || true

docs:
	@echo "Checking documentation with Vale..."
	vale --config audit/configs/vale.ini docs/ || true
	@echo "Linting Markdown files..."
	markdownlint '**/*.md' || true
	@echo "Checking for broken links..."
	lychee --verbose --no-progress '**/*.md' || true

audit: lint security test
	@echo "Full audit complete! Check audit/reports/ for detailed results."

update-deps:
	pip-compile requirements.in
	pip-compile requirements-dev.in
	pip-sync requirements.txt requirements-dev.txt

pre-commit-all:
	pre-commit run --all-files

# AWS-specific commands (requires AWS credentials)
aws-lambda-tune:
	python audit/scripts/lambda-power-tune.py

aws-cost-analyze:
	python audit/scripts/cost-analyzer.py

aws-dynamodb-optimize:
	python audit/scripts/dynamodb-optimizer.py

aws-dead-code:
	python audit/scripts/dead-code-detector.py src/

aws-full-audit: audit aws-lambda-tune aws-cost-analyze aws-dynamodb-optimize
	@echo "Complete AWS audit finished!"
