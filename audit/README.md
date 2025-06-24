# AWS Multi-Account Inventory - Audit Framework

This comprehensive audit framework provides automated code quality, security, and cost optimization analysis for the AWS Multi-Account Inventory system.

## Components

### 1. Pre-commit Hooks
Automated checks that run before each commit:
- **Ruff**: Python linting and formatting
- **Bandit**: Security vulnerability scanning
- **Vulture**: Dead code detection
- **detect-secrets**: Prevent committing secrets
- **cfn-nag**: CloudFormation security checks
- **tfsec**: Terraform security checks

### 2. GitHub Actions Workflows
Continuous integration pipelines:
- **Code Quality**: Linting, formatting, duplication checks
- **Security Scan**: Vulnerability scanning, dependency checks
- **Infrastructure Audit**: CloudFormation and Terraform validation
- **Performance Analysis**: Lambda optimization recommendations
- **Documentation Check**: Markdown quality and readability

### 3. Analysis Scripts
AWS-specific optimization tools:
- **lambda-power-tune.py**: Analyze Lambda memory usage and performance
- **cost-analyzer.py**: Identify cost optimization opportunities
- **dynamodb-optimizer.py**: DynamoDB table optimization
- **dead-code-detector.py**: Find unused code in the project

### 4. Monitoring Stack
CloudWatch alarms and anomaly detection:
- Lambda error rate monitoring
- Performance degradation alerts
- Cost anomaly detection
- Resource throttling alerts

## Quick Start

### Installation
```bash
# Install development dependencies
make install-dev

# Install pre-commit hooks
pre-commit install
```

### Running Audits

#### Local Code Quality Check
```bash
# Run all quality checks
make audit

# Individual checks
make lint       # Code linting
make security   # Security scanning
make test       # Unit tests
```

#### AWS Resource Analysis
```bash
# Analyze Lambda functions
make aws-lambda-tune

# Analyze costs
make aws-cost-analyze

# Full AWS audit
make aws-full-audit
```

#### Pre-commit Checks
```bash
# Run all pre-commit hooks
make pre-commit-all

# Run specific hook
pre-commit run ruff --all-files
```

## Configuration Files

### Tool Configurations
- **audit/configs/ruff.toml**: Python linting rules
- **audit/configs/bandit.yaml**: Security scan configuration
- **audit/configs/vale.ini**: Documentation style guide
- **.markdownlint.yml**: Markdown formatting rules

### GitHub Actions
All workflows are in `.github/workflows/`:
- Automatically triggered on pull requests
- Weekly scheduled scans for security and costs
- Results posted as PR comments

## Reports

All audit reports are saved to `audit/reports/`:
- **bandit-report.json**: Security vulnerabilities
- **lambda-performance-*.html**: Lambda optimization report
- **cost-analysis-*.json**: Cost optimization opportunities
- **dynamodb-optimization-*.html**: DynamoDB analysis

## Best Practices

1. **Pre-commit**: Always run `make pre-commit-all` before pushing
2. **Regular Audits**: Schedule weekly `make aws-full-audit`
3. **Act on Findings**: Review and implement optimization recommendations
4. **Update Dependencies**: Keep tools updated with `make update-deps`

## Customization

### Adding New Checks
1. Add tool to `requirements-dev.txt`
2. Configure in `.pre-commit-config.yaml`
3. Create GitHub Action workflow if needed

### Adjusting Thresholds
Edit configuration files in `audit/configs/` to adjust:
- Linting rules severity
- Security check sensitivity
- Documentation standards

## Troubleshooting

### Common Issues

1. **Pre-commit hook failures**
   ```bash
   # Skip hooks temporarily
   git commit --no-verify
   
   # Fix issues and run
   make pre-commit-all
   ```

2. **AWS credential errors**
   ```bash
   # Ensure AWS credentials are configured
   aws configure
   
   # Or use environment variables
   export AWS_PROFILE=your-profile
   ```

3. **Tool installation issues**
   ```bash
   # Reinstall all tools
   pip install -r requirements-dev.txt --force-reinstall
   ```

## Contributing

1. Ensure all pre-commit hooks pass
2. Add tests for new features
3. Update documentation
4. Follow the code style guidelines

## Support

For issues or questions:
1. Check existing GitHub issues
2. Review workflow logs in GitHub Actions
3. Contact the security team for security-related concerns