# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions to automate testing, security scanning, quality checks, and deployment processes. The pipeline is designed to catch bugs early, enforce code quality standards, and ensure security before code reaches production.

## Workflows

### 1. **ci.yml** - Main Continuous Integration
**Trigger**: Push to any branch, Pull Requests

**Jobs**:
- **lint**: Code style and linting checks
  - Black formatting validation
  - isort import sorting
  - Flake8 linting
  - Mypy type checking
  - All checks must pass (no continue-on-error)

- **test**: Unit tests and coverage
  - Runs pytest across Python 3.11, 3.12, 3.13
  - Generates coverage report
  - Enforces minimum 70% code coverage
  - Uploads coverage to artifact

- **security**: Security vulnerability scanning
  - Bandit code security scan
  - Safety dependency vulnerability check
  - Secrets detection with gitleaks

- **build**: Application build verification
  - Validates Flask app syntax
  - Checks import statements
  - Builds package distribution

- **api-tests**: Smoke tests for Flask API
  - Verifies Flask app starts
  - Tests homepage endpoint
  - Validates basic API functionality

- **success**: Aggregation job
  - Depends on all critical jobs
  - Only runs if all checks pass
  - Blocks merge if any job fails

### 2. **quality.yml** - Advanced Code Quality
**Trigger**: Push to develop/main, Scheduled daily at 3 AM UTC

**Jobs**:
- **type-checking**: Comprehensive type checking
  - Runs Mypy across all Python versions
  - Generates HTML type report

- **security-scan**: Deep security analysis
  - Bandit detailed scan
  - Safety vulnerability audit
  - Semgrep static code analysis

- **secrets-detection**: Secret leak prevention
  - TruffleHog scans entire repo history
  - Detects leaked API keys, credentials, tokens

- **coverage-enforcement**: Coverage validation
  - Runs pytest with coverage
  - Enforces 70% minimum threshold
  - Uploads HTML coverage report as artifact

- **schema-validation**: Database validation
  - Checks for migration files
  - Validates SQL files present
  - Ensures schema documentation exists

- **docs-quality**: Documentation checks
  - Validates documentation exists
  - Markdown linting
  - Checks for docstrings in code

- **dependency-audit**: Dependency health
  - pip-audit for known vulnerabilities
  - Detects outdated packages
  - Reports security advisories

- **performance-check**: Performance metrics
  - Cyclomatic complexity analysis (Radon)
  - Maintainability index calculation
  - Identifies overly complex functions

- **quality-summary**: Summary aggregation
  - Reports all quality check results
  - Provides actionable feedback

### 3. **deploy.yml** - Deployment Pipeline
**Trigger**: Push to main, Manual workflow_dispatch

**Jobs**:
- **pre-deployment-checks**: Validation before deploy
  - Mypy type checking
  - Bandit security scan
  - Safety vulnerability check
  - Flask syntax verification
  - Unit test execution
  - Blocks deployment if any check fails

- **deploy**: Application deployment
  - Requires pre-deployment-checks to pass
  - Installs dependencies
  - Creates deployment tag (YYYYMMdd_HHMMSS format)
  - Logs deployment information
  - Generates deployment summary

- **smoke-tests**: Post-deployment validation
  - Waits for deploy job to complete
  - Runs smoke test suite
  - Validates app is running correctly

- **notify-success**: Success notification
  - Only runs if all jobs pass
  - Notifies team of successful deployment

### 4. **advanced-checks.yml** - Comprehensive Quality Suite
**Trigger**: Push to main/develop/feature branches, Scheduled daily

**Jobs**:
Multiple quality and security checks (see quality.yml section above)

## Local Development Setup

### Install Development Dependencies

```bash
# Install dev tools
pip install -r requirements-dev.txt

# Or install just essentials
pip install black isort flake8 mypy pytest pytest-cov
```

### Pre-Commit Hook Setup (Optional)

```bash
pip install pre-commit

# Create .pre-commit-config.yaml in project root
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/PyCQA/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=120, --extend-ignore=E203]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-flask]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [--ll]
EOF

# Install pre-commit hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

### Running Checks Locally

```bash
# Format code
black flask_app/ factor-lab/src/ tests/
isort flask_app/ factor-lab/src/ tests/

# Lint
flake8 flask_app/ factor-lab/src/ tests/

# Type checking
mypy flask_app/ factor-lab/src/ --ignore-missing-imports

# Security scanning
bandit -r flask_app/ factor-lab/src/ -ll

# Tests and coverage
pytest tests/ --cov=flask_app --cov=factor-lab/src --cov-report=html

# Check for vulnerabilities
safety check
```

## GitHub Branch Protection Rules

To enforce CI/CD checks, configure branch protection:

1. Go to **Settings → Branches → Branch protection rules**
2. Add rule for `main` branch:
   - ✅ Require status checks to pass before merging:
     - `ci / lint`
     - `ci / test`
     - `ci / security`
     - `ci / build`
     - `ci / success`
   - ✅ Require code reviews before merging (at least 1)
   - ✅ Dismiss stale pull request approvals
   - ✅ Require branches to be up to date before merging
   - ✅ Require conversation resolution before merging

## Minimum Coverage Threshold

The pipeline enforces **70% code coverage** minimum:
- If coverage falls below 70%, tests fail
- Coverage report is uploaded to artifacts
- View detailed coverage: Check "coverage-report" artifact in workflow run

To update threshold:
- Edit `ci.yml` line with `--cov-fail-under=70`
- Update to desired percentage
- Commit and push

## Security Scanning Details

### Bandit (Code Security)
- Scans for common security vulnerabilities
- Checks for hardcoded passwords, SQL injection, insecure functions
- Runs at `-ll` (LOW level) to catch more issues
- Continue-on-error: true (reports but doesn't block)

### Safety (Dependency Vulnerabilities)
- Checks for known vulnerabilities in installed packages
- Uses vulnerability database
- Recommends package upgrades
- Continue-on-error: true

### Semgrep (Advanced Analysis)
- Detects complex security patterns
- Uses OWASP security audit config
- JSON output for parsing
- Continue-on-error: true

### TruffleHog (Secrets Detection)
- Scans git history for leaked secrets
- Detects API keys, credentials, tokens
- Only verifies high-confidence matches
- Fails CI if secrets detected

## Type Checking with Mypy

Mypy validates Python type hints across Python versions:

```bash
# Install type stubs
pip install types-requests types-flask

# Run mypy
mypy flask_app/ factor-lab/src/ --ignore-missing-imports

# Generate HTML report
mypy --html htmlcov/mypy flask_app/ factor-lab/src/
```

## Test Coverage Rules

```python
# Good: Function has type hints and docstring
def analyze_stock(symbol: str, days: int = 30) -> Dict[str, float]:
    """Analyze stock performance over N days.
    
    Args:
        symbol: Stock ticker symbol
        days: Number of days to analyze
        
    Returns:
        Dictionary of analysis metrics
    """
    # Implementation
    pass

# Avoid: No type hints, no docstring
def analyze(stock, n):
    # Implementation
    pass
```

## Deployment Workflow

```
Feature Branch → Push
        ↓
  CI Pipeline Runs
  - lint ✓
  - test ✓
  - security ✓
  - build ✓
  - api-tests ✓
        ↓
  Create Pull Request
        ↓
  Code Review Required
        ↓
  Merge to main
        ↓
  Deploy Pipeline Triggers
  - pre-deployment-checks ✓
  - deploy ✓
  - smoke-tests ✓
  - notify-success ✓
        ↓
  Production Live ✅
```

## Troubleshooting

### Black Formatting Issues
```bash
# Auto-format entire codebase
black flask_app/ factor-lab/src/ tests/

# Check what black would change (dry-run)
black --check flask_app/ factor-lab/src/ tests/
```

### Mypy Type Errors
```bash
# Run with more verbose output
mypy flask_app/ --pretty --show-error-codes --show-column-numbers

# Ignore specific errors temporarily (use sparingly)
# Add to function or file: # type: ignore
```

### Coverage Below Threshold
```bash
# Generate detailed coverage report
pytest tests/ --cov=flask_app --cov=factor-lab/src --cov-report=html

# Open htmlcov/index.html to see which files need coverage
# Add tests for low-coverage files

# Current minimum: 70% (can be increased)
```

### Failed Security Scans
```bash
# Review bandit findings
bandit -r flask_app/ factor-lab/src/ -v

# False positives can be marked with comments:
# nosec - marks line as reviewed and safe

# Example:
import pickle  # nosec - safe in this context
```

## Performance Metrics

The pipeline generates performance metrics:

- **Cyclomatic Complexity**: Measures code flow complexity
  - A: 1-5 (simple)
  - B: 6-10 (moderate)
  - C: 11-20 (complex)
  - D: 21-40 (very complex)
  - E: 41+ (too complex)

- **Maintainability Index**: Overall code maintainability (0-100)
  - 100-81: Highly maintainable
  - 80-51: Moderate maintainability  
  - 50-0: Low maintainability

Aim for:
- Most functions: Complexity A or B
- Maintainability: > 80

## Continuous Monitoring

The `advanced-checks.yml` workflow runs daily at **3 AM UTC** to:
- Detect new security vulnerabilities
- Track code quality trends
- Monitor dependency health
- Identify outdated packages

Review results in **Actions → Advanced Quality Checks** dashboard.

## FAQ

**Q: Why does CI block merge if coverage drops?**
A: Prevents accumulation of untested code. Tests catch bugs early, reduce production issues.

**Q: Can I skip security checks?**
A: Not recommended. Security scans catch real vulnerabilities. Review findings, add `# nosec` only if truly safe.

**Q: How often do I need to update dependencies?**
A: Review weekly. Update patch versions (1.2.3 → 1.2.4) anytime. Test major versions before updating.

**Q: What if type hints are incomplete?**
A: Use `# type: ignore` temporarily, but add proper hints soon. Gradual typing is fine, aim for 80%+ coverage.

**Q: How do I run the full CI locally?**
A: Use `act` tool: `brew install act` then `act` in repo root (simulates GitHub Actions).

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Mypy Type Checking](https://mypy.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Bandit Security](https://bandit.readthedocs.io/)
- [Black Code Formatter](https://black.readthedocs.io/)
