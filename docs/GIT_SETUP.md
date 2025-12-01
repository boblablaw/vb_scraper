# Git Setup Guide

This guide will help you set up your local repository and connect it to GitHub.

## Repository Information

- **GitHub URL**: https://github.com/boblablaw/vb_scraper
- **SSH URL**: git@github.com:boblablaw/vb_scraper.git
- **HTTPS URL**: https://github.com/boblablaw/vb_scraper.git

## Initial Setup

### Option A: Clone Existing Repository (Recommended for new setup)

If you're starting fresh, clone the repository:

```bash
# Using SSH (recommended)
git clone git@github.com:boblablaw/vb_scraper.git
cd vb_scraper

# Or using HTTPS
git clone https://github.com/boblablaw/vb_scraper.git
cd vb_scraper
```

### Option B: Connect Existing Local Repository

If you already have a local repository, connect it to GitHub:

```bash
# Add GitHub as remote
git remote add origin git@github.com:boblablaw/vb_scraper.git

# Verify remote was added
git remote -v

# Push your code
git push -u origin main
```

## SSH Authentication Setup

### Check for Existing SSH Keys

```bash
ls -la ~/.ssh/*.pub
```

### Generate New SSH Key (if needed)

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Press Enter to accept default location
# Enter a passphrase (recommended) or press Enter to skip
```

### Add SSH Key to ssh-agent

```bash
# Start ssh-agent
eval "$(ssh-agent -s)"

# Add your SSH key
ssh-add ~/.ssh/id_ed25519
```

### Add SSH Key to GitHub

1. Display your public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```

2. Copy the entire output (starts with `ssh-ed25519`)

3. Go to https://github.com/settings/keys

4. Click **"New SSH key"**

5. Give it a title (e.g., "MacBook Pro")

6. Paste your public key

7. Click **"Add SSH key"**

### Test SSH Connection

```bash
ssh -T git@github.com
```

You should see: `Hi boblablaw! You've successfully authenticated...`

(Exit code 1 is expected - this is normal)

## Alternative: HTTPS Authentication

If you prefer HTTPS over SSH:

```bash
# Remove SSH remote (if already added)
git remote remove origin

# Add HTTPS remote
git remote add origin https://github.com/boblablaw/vb_scraper.git

# Push (will prompt for credentials)
git push -u origin main
```

For HTTPS, you'll need a Personal Access Token:
- Go to https://github.com/settings/tokens
- Click "Generate new token (classic)"
- Select scopes: `repo` (full control of private repositories)
- Use the token as your password when pushing

## Common Git Workflows

### Daily Development

```bash
# Check status
git status

# Add changes
git add .

# Commit changes
git commit -m "Description of changes"

# Push to GitHub
git push
```

### Pull Latest Changes

```bash
# Fetch and merge changes from GitHub
git pull

# Or fetch first, then merge
git fetch origin
git merge origin/main
```

### Create a Branch

```bash
# Create and switch to new branch
git checkout -b feature-name

# Push branch to GitHub
git push -u origin feature-name

# Switch back to main
git checkout main
```

### Check Remote Configuration

```bash
# View remote URLs
git remote -v

# View detailed remote info
git remote show origin
```

## Troubleshooting

### Permission Denied (publickey)

If you see this error:
```
git@github.com: Permission denied (publickey)
```

Solutions:
1. Make sure your SSH key is added to GitHub (see above)
2. Ensure ssh-agent is running: `eval "$(ssh-agent -s)"`
3. Add your key to the agent: `ssh-add ~/.ssh/id_ed25519`
4. Test connection: `ssh -T git@github.com`

### Wrong Remote URL

To change from HTTPS to SSH (or vice versa):

```bash
# View current remote
git remote -v

# Change to SSH
git remote set-url origin git@github.com:boblablaw/vb_scraper.git

# Or change to HTTPS
git remote set-url origin https://github.com/boblablaw/vb_scraper.git
```

### Divergent Branches

If you have commits locally and on GitHub that diverge:

```bash
# Pull with rebase to keep clean history
git pull --rebase origin main

# Or merge (creates merge commit)
git pull origin main
```

## Best Practices

1. **Commit often** with clear, descriptive messages
2. **Pull before pushing** to avoid conflicts
3. **Use branches** for new features or experiments
4. **Test before committing** - run tests to ensure code works
5. **Keep commits focused** - one logical change per commit
6. **Write good commit messages**:
   - First line: Brief summary (50 chars or less)
   - Blank line
   - Detailed explanation if needed

### Example Commit Message

```
Add position normalization for MH (Middle Hitter)

- Updated extract_position_codes() to recognize MH as MB
- Added test cases for MH position mapping
- Updated WARP.md documentation
```

## Additional Resources

- [GitHub SSH Documentation](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [Git Basics](https://git-scm.com/book/en/v2/Getting-Started-Git-Basics)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
