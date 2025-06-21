.PHONY: help install test deploy collect query

help:
	@echo "AWS Multi-Account Inventory"
	@echo "make install  - Install dependencies"
	@echo "make deploy   - Deploy infrastructure"
	@echo "make collect  - Run inventory collection"
	@echo "make query    - Query inventory"

install:
	pip install -r requirements.txt

deploy:
	./scripts/deploy.sh all

collect:
	python src/collector/main.py --config config/accounts.json

query:
	python src/query/inventory_query.py --action summary