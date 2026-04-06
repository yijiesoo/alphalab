# Branch Protection & GitHub Setup

## Setup Instructions

### 1. Enable Branch Protection for Main

Go to GitHub Repository → Settings → Branches

Click "Add rule" and configure for `main`:

**Protection Settings:**
- ✅ Require a pull request before merging
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require review from Code Owners
- ✅ Require status checks to pass before merging
  - Select: `CI/CD Pipeline`
  - Select: `Code Quality & Documentation`
- ✅ Include administrators
- ✅ Allow auto-merge

### 2. Required Status Checks

In branch protection rules, select these as required:

- `lint` (Python 3.11, 3.12, 3.13)
- `test` (Python 3.11, 3.12, 3.13)
- `security`
- `build`

### 3. Code Owners (Optional)

Create `.github/CODEOWNERS` file:

```
# Repository code owners

# Stock analysis features
flask_app/app.py @yijiesoo
factor-lab/src/ @yijiesoo

# Configuration
*.yml @yijiesoo
.env* @yijiesoo

# Tests
tests/ @yijiesoo
```

### 4. Pull Request Template

Create `.github/pull_request_template.md`:

```markdown
## Description
Briefly describe the changes made.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Enhancement
- [ ] Documentation update

## Related Issues
Closes #issue_number

## Testing Done
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Changes are well documented
- [ ] No new warnings generated
- [ ] Tests added/updated
- [ ] No breaking changes

## Screenshots (if applicable)
Add screenshots for UI changes
```

### 5. GitHub Actions Secrets (if needed)

Go to Settings → Secrets and Variables → Actions

Click "New repository secret" and add:

```
DEPLOY_KEY = <your-deploy-key>
SLACK_WEBHOOK = <your-webhook-url>
```

### 6. Enable Auto-merge (Optional)

Allows PRs to auto-merge when all checks pass.

## Workflow Rules

### For Feature Branches
```
feature/* → create PR → CI runs → Review & Approve → Merge to develop
```

### For Main Branch
```
develop → create PR → CI/CD runs → Security review → Merge to main → Auto-deploy
```

## Commands to Verify Setup

```bash
# Check branch protection
gh repo view --json branchProtectionRules

# List all workflows
gh workflow list

# View workflow status
gh run list --branch main

# Trigger workflow manually
gh workflow run ci.yml --ref main
```

## First Time Setup Checklist

- [ ] Clone repository
- [ ] Copy `.env.example` to `.env`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run local checks: `black`, `flake8`, `pytest`
- [ ] Push to feature branch
- [ ] Create PR to `develop`
- [ ] Wait for CI checks to pass
- [ ] Get code review
- [ ] Merge to `main`
- [ ] Verify deployment

---

**For More Info**: See `.github/CI_CD_GUIDE.md`
