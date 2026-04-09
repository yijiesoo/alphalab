# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions to automate testing, quality checks, security scanning, and deployment. The pipeline currently runs checks in a non-blocking mode (most steps use `continue-on-error: true`) to provide visibility without failing builds.

## Workflows

### 1. **ci.yml** - Main Continuous Integration
**Trigger**: Push to `main`/`develop`, Pull Requests to `main`/`develop`

**Jobs**:
- **test**: Runs the unit test suite
  - Python 3.12
  - Installs `pytest`, `pytest-cov`, and `requirements.txt`
  - Runs `pytest tests/ -v --tb=short`
  - Both install and test steps use `continue-on-error: true` (non-blocking)

### 2. **quality.yml** - Code Quality Analysis
**Trigger**: Push to `main`/`develop`, Pull Requests to `main`/`develop`

**Jobs**:
- **quality**: Runs code analysis tools
  - Pylint static analysis (`--exit-zero`, non-blocking)
  - pip-audit for known dependency vulnerabilities (non-blocking)
  - Reports outdated packages (non-blocking)

### 3. **deploy.yml** - Deployment Pipeline
**Trigger**: Push to `main`, Manual `workflow_dispatch`

**Jobs**:
- **deploy**: Deploys the application
  - Installs Python 3.12 and `requirements.txt`
  - Runs `pytest tests/` with `continue-on-error: true` (non-blocking)
  - Logs deployment info (commit SHA and timestamp)

### 4. **advanced-checks.yml** - Comprehensive Quality Suite
**Trigger**: Push to `main`/`develop`/`feature/*`, Pull Requests to `main`/`develop`, Scheduled daily at 3 AM UTC

**Jobs** (all security/quality jobs use `continue-on-error: true` except secrets-detection and coverage-enforcement):
- **type-checking**: Mypy type checking across Python 3.11, 3.12, 3.13
- **security-scan**: Bandit, Safety, and Semgrep static analysis
- **secrets-detection**: TruffleHog scanning for leaked credentials (blocking)
- **coverage-enforcement**: pytest with coverage, enforces 70% minimum threshold, uploads HTML coverage artifact
- **schema-validation**: Checks for SQL/migration files in the repo
- **docs-quality**: Checks for README/docs presence, pydocstyle, markdown validation
- **dependency-audit**: pip-audit and outdated package detection
- **performance-check**: Radon cyclomatic complexity and maintainability index
- **quality-summary**: Aggregates and summarises all check results

## Local Development Setup

### Install Development Dependencies

```bash
pip install -r requirements.txt
pip install pytest pytest-cov pylint mypy bandit safety pip-audit radon
```

### Running Checks Locally

```bash
# Run tests
pytest tests/ -v --tb=short

# Tests with coverage
pytest tests/ --cov=flask_app --cov=factor-lab/src --cov-report=html

# Pylint static analysis
pylint flask_app/ factor-lab/src/ --exit-zero

# Type checking
mypy flask_app/ factor-lab/src/ --ignore-missing-imports

# Security scanning
bandit -r flask_app/ factor-lab/src/ -ll

# Dependency vulnerability audit
pip-audit

# Cyclomatic complexity
radon cc flask_app/ factor-lab/src/ -a

# Maintainability index
radon mi flask_app/ factor-lab/src/ -s
```

## GitHub Branch Protection Rules

To enforce CI/CD checks, configure branch protection:

1. Go to **Settings → Branches → Branch protection rules**
2. Add rule for `main` branch:
   - ✅ Require status checks to pass before merging:
     - `Run Tests` (from ci.yml)
   - ✅ Require code reviews before merging (at least 1)
   - ✅ Dismiss stale pull request approvals
   - ✅ Require branches to be up to date before merging
   - ✅ Require conversation resolution before merging

> **Note**: Most workflow steps currently use `continue-on-error: true`, so they do not block merges. To make tests a hard gate, remove `continue-on-error` from the test step in `ci.yml`.

## Minimum Coverage Threshold

The `advanced-checks.yml` `coverage-enforcement` job enforces a **70% code coverage** minimum:
- If coverage falls below 70%, that job fails
- HTML coverage report is uploaded to GitHub Actions artifacts as `coverage-report`
- View detailed coverage: Check the **coverage-report** artifact in the `Advanced Quality Checks` workflow run

To update the threshold:
- Edit `advanced-checks.yml` line with `--fail-under=70`
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
  CI Pipeline Runs (ci.yml)
  - test (continue-on-error)
        ↓
  Quality Pipeline Runs (quality.yml)
  - pylint, pip-audit (continue-on-error)
        ↓
  Create Pull Request
        ↓
  Code Review Required
        ↓
  Merge to main
        ↓
  Deploy Pipeline Triggers (deploy.yml)
  - install dependencies
  - run tests (continue-on-error)
  - log deployment info
        ↓
  Production Live ✅
```

## Troubleshooting

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

# Current minimum: 70% (enforced in advanced-checks.yml coverage-enforcement job)
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

**Q: Why don't failed tests block CI merges?**
A: Currently most steps use `continue-on-error: true` for visibility. To make tests a hard gate, remove `continue-on-error` from the test step in `ci.yml` and configure branch protection rules to require the `Run Tests` status check.

**Q: Where is the 70% coverage threshold enforced?**
A: In `advanced-checks.yml`, the `coverage-enforcement` job calls `coverage report --fail-under=70` and will fail if coverage drops below 70%.

**Q: Can I skip security checks?**
A: Not recommended. Security scans catch real vulnerabilities. Review findings, add `# nosec` only if truly safe.

**Q: How often do I need to update dependencies?**
A: Review weekly. Update patch versions (1.2.3 → 1.2.4) anytime. Test major versions before updating.

**Q: What if type hints are incomplete?**
A: Use `# type: ignore` temporarily, but add proper hints soon. Gradual typing is fine, aim for 80%+ type coverage.

**Q: How do I run the full CI locally?**
A: Use `act` tool: `brew install act` then `act` in repo root (simulates GitHub Actions).

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Mypy Type Checking](https://mypy.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Bandit Security](https://bandit.readthedocs.io/)
- [Black Code Formatter](https://black.readthedocs.io/)
