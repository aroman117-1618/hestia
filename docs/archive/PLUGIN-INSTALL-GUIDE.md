# Hestia Plugin Installation Guide

These plugins should be installed via the Claude Code CLI on your development machine (MacBook).

## Required Plugins

### 1. Pyright LSP — Real-Time Python Type Checking

Gives Claude real-time diagnostics from Pyright. After every edit, type errors, unresolved imports, and schema violations surface immediately.

**Why**: Hestia has 19K+ lines of Python with type hints throughout but no enforced type checking. This closes that gap automatically.

```bash
# Step 1: Install Pyright
pip install pyright

# Step 2: Install the Claude Code plugin
claude plugin install pyright-lsp@claude-plugins-official
```

### 2. GitHub — Source Control Integration

Native access to GitHub issues, PRs, branches, and actions.

**Why**: Streamlines PR workflows and repository management without leaving the conversation.

```bash
claude plugin install github@claude-plugins-official
```

### 3. Commit Commands — Git Workflow Skills

Slash commands for standardized commits, branch management, and changelog generation.

**Why**: Consistent commit messages and git workflow discipline.

```bash
claude plugin install commit-commands@claude-plugins-official
```

### 4. PR Review Toolkit — Pull Request Review

Specialized sub-agents for structured PR review (security, performance, coverage).

**Why**: Multi-dimensional PR review before merge.

```bash
claude plugin install pr-review-toolkit@claude-plugins-official
```

## Verification

After installation, verify all plugins are active:

```bash
claude plugin list
```

You should see all four plugins listed and enabled.

## Notes

- Plugins are installed **user-scoped** by default. For project-scoped installation (recommended for Hestia), add `--scope project` to install commands.
- Plugin availability may vary — check `claude plugin marketplace` if installation fails.
- These commands should be run in the terminal, not in Cowork mode.
- If the exact plugin names have changed, check the official marketplace: `claude plugin marketplace`
