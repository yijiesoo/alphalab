# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions for automated testing, linting, security checks, and deployment. The pipeline runs on every push and pull request to ensure code quality and reliability.

## Workflows

### 1. **CI Pipeline** (`ci.yml`)
Runs on every push to any branch and all pull requests.

**Jobs:**
- **Lint & Code Quality**: Runs Black formatter, isort, and Flake8 checks
- **Tests**: Runs pytest with coverage reporting
- **Security**: Scans for vulnerabilities with Bandit and Safety
- **Secrets Check**: Detects accidentally committed secrets
- **Build**: Builds the Python package

**Triggers:**
- Push to `main`, `develop`, or `feature/*` branches
- Pull requests to `main` or `develop`

**Status Checks:**
- ✅ All checks pass before allowing merge to main

### 2. **Deploy Pipeline** (`deploy.yml`)
Runs automatically when code is pushed to `main`, or manually with workflow dispatch.

**Jobs:**
- **Deploy**: Prepares and validates deployment
- **Smoke Tests**: Runs integration tests after deployment
- **Notify Success**: Sends deployment notification

**Features:**
- Creates deployment tags with timestamps
- Generates deployment summaries
- Pre-deployment health checks

**Manual Trigger:**
```bash
# Via GitHub CLI
gh workflow run deploy.yml --ref main
```

### 3. **Code Quality** (`quality.yml`)
Runs on push to main/develop, pull requests, and daily schedule.

**Jobs:**
- **Code Quality Analysis**: Pylint, complexity analysis (Radon)
- **Documentation Check**: Validates README and CHANGELOG
- **Dependency Audit**: Checks for outdated/vulnerable packages

**Schedule:**
- Runs daily at 2 AM UTC
- Can be triggered manually

## Branch Strategy

```
main
├── [Protected] Requires passing CI/CD checks
├── [Requires PR review]
└── [Auto-deploys when merged]

develop
├── [Integration branch]
├── [Requires passing CI checks]
└── [Manual deployment]

feature/*
├── [Feature branches]
├── [Runs CI checks]
└── [Requires PR to develop/main]
```

## Getting Started

### 1. **Push to Feature Branch**
```bash
git checkout -b feature/your-feature
git add .
git commit -m "Add your feature"
git push origin feature/your-feature
```

### 2. **Create Pull Request**
- Go to GitHub and create a PR to `develop` or `main`
- CI pipeline runs automatically
- Review checks before merging

### 3. **Merge to Main**
```bash
# Via GitHub (recommended)
- Merge PR in GitHub UI
- Deploy workflow triggers automatically

# Via CLI
git checkout main
git pull origin main
git merge feature/your-feature
git push origin main
```

## Local Development

### Install Development Tools
```bash
pip install -r requirements.txt
pip install black isort flake8 pylint pytest pytest-cov
```

### Run Checks Locally (Before Pushing)
```bash
# Format code
black flask_app/ factor-lab/src/

# Sort imports
isort flask_app/ factor-lab/src/

# Lint
flake8 flask_app/ factor-lab/src/

# Run tests
pytest tests/ -v --cov

# Security scan
bandit -r flask_app/ factor-lab/src/
```

### Pre-commit Hook (Optional)
Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
echo "Running pre-commit checks..."
black --check flask_app/ factor-lab/src/ || exit 1
flake8 flask_app/ factor-lab/src/ || exit 1
pytest tests/ -q || exit 1
echo "✅ All checks passed!"
```

## Status Checks

All workflows must pass for main:

- ✅ **CI Pipeline** (lint, test, security, build)
- ✅ **Code Quality** 
- ✅ **Branch Protection Rules**

## Troubleshooting

### CI Pipeline Failures

**Flake8 Errors:**
```bash
black flask_app/ factor-lab/src/
isort flask_app/ factor-lab/src/
```

**Test Failures:**
```bash
pytest tests/ -v --tb=short
```

**Import Errors:**
```bash
pip install -r requirements.txt
```

### Secrets Detected

If TruffleHog detects a secret:
1. Remove the file from Git history
2. Rotate the credential immediately
3. Add to `.gitignore`

```bash
# Remove from history
git filter-branch --tree-filter 'rm -f path/to/secret' HEAD

# Force push
git push origin main --force
```

## Deployment Process

### Automatic Deployment (Main Branch)
1. Push to `main`
2. GitHub Actions runs CI checks
3. All checks pass → Deploy workflow runs
4. Smoke tests validate deployment
5. Success notification sent

### Manual Deployment
```bash
gh workflow run deploy.yml --ref main
```

## Environment Variables

Required in GitHub Secrets for deployment:

- `FIREBASE_WEB_API_KEY` (already in .env)
- `SUPABASE_URL` (already in .env)
- `SUPABASE_ANON_KEY` (already in .env)

**Never commit:** `.env` files containing credentials

## Monitoring

### View Workflow Runs
```bash
# List all workflows
gh workflow list

# View recent runs
gh run list

# Watch specific run
gh run watch <run-id>
```

### Badges
Add to README.md:
```markdown
![CI/CD](https://github.com/yijiesoo/alphalab/actions/workflows/ci.yml/badge.svg)
![Deploy](https://github.com/yijiesoo/alphalab/actions/workflows/deploy.yml/badge.svg)
```

## Best Practices

1. **Always create PRs** - Never push directly to main
2. **Run checks locally** - Before pushing, run linters and tests
3. **Keep commits atomic** - One feature per commit
4. **Write descriptive messages** - Help reviewers understand changes
5. **Review logs** - Check workflow logs if something fails
6. **Tag releases** - Use semver tags for releases

## Support

For CI/CD issues:
- Check workflow logs in GitHub Actions
- Review error messages
- Run checks locally to debug
- Consult GitHub Actions documentation

---

**Last Updated**: April 6, 2026
**Maintained by**: Development Team
