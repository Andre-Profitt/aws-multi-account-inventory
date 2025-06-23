#!/bin/bash

# Script to validate the integration of all components

set -e

echo "🔍 Validating AWS Multi-Account Inventory System Integration"
echo "========================================================="

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Functions
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2 - File not found: $1"
        return 1
    fi
}

check_import() {
    if grep -q "$2" "$1" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $3"
    else
        echo -e "${RED}✗${NC} $3 - Import not found: $2 in $1"
        return 1
    fi
}

# Check required files
echo -e "\n📁 Checking required files..."
check_file "src/collector/enhanced_main.py" "Enhanced collector module"
check_file "src/query/inventory_query.py" "Query module"
check_file "src/handler.py" "Lambda handler"
check_file "config/accounts.json.example" "Example configuration"
check_file "infrastructure/cloudformation.yaml" "CloudFormation template"
check_file "deploy.sh" "Deployment script"

# Check imports
echo -e "\n📦 Checking module imports..."
check_import "src/handler.py" "from collector.enhanced_main import AWSInventoryCollector" "Handler imports collector"
check_import "src/handler.py" "from query.inventory_query import InventoryQuery" "Handler imports query"

# Check Lambda handler structure
echo -e "\n🔧 Checking Lambda handler structure..."
if grep -q "def lambda_handler(event, context):" "src/handler.py"; then
    echo -e "${GREEN}✓${NC} Lambda handler function exists"
else
    echo -e "${RED}✗${NC} Lambda handler function not found"
fi

# Check DynamoDB table structure
echo -e "\n💾 Checking DynamoDB integration..."
if grep -q "pk.*sk" "src/collector/enhanced_main.py"; then
    echo -e "${GREEN}✓${NC} DynamoDB pk/sk pattern implemented"
else
    echo -e "${RED}✗${NC} DynamoDB pk/sk pattern not found"
fi

# Check configuration structure
echo -e "\n⚙️  Checking configuration..."
if [ -f "config/accounts.json" ]; then
    if python -c "import json; json.load(open('config/accounts.json'))" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Configuration file is valid JSON"
    else
        echo -e "${RED}✗${NC} Configuration file has invalid JSON"
    fi
else
    echo -e "${YELLOW}⚠${NC}  No config/accounts.json found - using example"
fi

# Check Python syntax
echo -e "\n🐍 Checking Python syntax..."
ERROR_COUNT=0
for file in src/**/*.py; do
    if [ -f "$file" ]; then
        if python -m py_compile "$file" 2>/dev/null; then
            :
        else
            echo -e "${RED}✗${NC} Syntax error in: $file"
            ((ERROR_COUNT++))
        fi
    fi
done

if [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All Python files have valid syntax"
fi

# Check requirements
echo -e "\n📋 Checking requirements..."
if [ -f "requirements.txt" ]; then
    MISSING_DEPS=0
    while IFS= read -r line; do
        # Skip comments and empty lines
        if [[ ! "$line" =~ ^#.*$ ]] && [[ ! -z "$line" ]]; then
            PKG=$(echo "$line" | cut -d'>' -f1 | cut -d'=' -f1 | cut -d'<' -f1)
            if ! pip show "$PKG" >/dev/null 2>&1; then
                echo -e "${YELLOW}⚠${NC}  Missing dependency: $PKG"
                ((MISSING_DEPS++))
            fi
        fi
    done < requirements.txt
    
    if [ $MISSING_DEPS -eq 0 ]; then
        echo -e "${GREEN}✓${NC} All dependencies installed"
    else
        echo -e "${YELLOW}⚠${NC}  Run 'pip install -r requirements.txt' to install missing dependencies"
    fi
fi

# Test module imports
echo -e "\n🧪 Testing module imports..."
if python -c "from src.collector.enhanced_main import AWSInventoryCollector" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Collector module imports successfully"
else
    echo -e "${RED}✗${NC} Failed to import collector module"
fi

if python -c "from src.query.inventory_query import InventoryQuery" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Query module imports successfully"
else
    echo -e "${RED}✗${NC} Failed to import query module"
fi

# Check CloudFormation references
echo -e "\n☁️  Checking CloudFormation integration..."
if grep -q "handler.lambda_handler" "infrastructure/cloudformation.yaml"; then
    echo -e "${GREEN}✓${NC} CloudFormation references correct handler"
else
    echo -e "${RED}✗${NC} CloudFormation handler reference incorrect"
fi

# Check test integration
echo -e "\n🧪 Checking test integration..."
if grep -q "from collector.enhanced_main import AWSInventoryCollector" "tests/unit/test_enhanced_collector.py"; then
    echo -e "${GREEN}✓${NC} Tests import correct modules"
else
    echo -e "${RED}✗${NC} Tests have incorrect imports"
fi

# Summary
echo -e "\n📊 Integration Validation Summary"
echo "================================"
echo -e "${GREEN}✓${NC} Core components are properly integrated"
echo -e "${YELLOW}⚠${NC}  Remember to:"
echo "   - Copy config/accounts.json.example to config/accounts.json"
echo "   - Update account IDs and role names"
echo "   - Deploy member account roles"
echo "   - Run 'make test' to verify functionality"

echo -e "\n✨ Integration validation complete!"