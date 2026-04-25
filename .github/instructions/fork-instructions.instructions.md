# Fork Instructions — Contributing Back to Upstream

This document covers what to do when you want to cherry-pick a commit from
this fork (`cest-la-v/ComfyUI`) and submit it as a pull request to the
upstream repo (`Comfy-Org/ComfyUI`).

---

## Prerequisites

Before opening any PR to upstream, read the upstream contribution guide:

- **CONTRIBUTING.md**: "For general improvements/bug fixes just make a pull request."
- **Wiki**: Model-architecture PRs have an additional checklist; bug fixes do not.

---

## Step-by-step: Cherry-pick to a new branch and open a PR

```bash
# 1. Create a branch off the latest upstream HEAD (not your fork's dev)
git checkout -b fix/your-fix-name upstream/master

# 2. Cherry-pick your commit
git cherry-pick <commit-sha>

# 3. Strip the Copilot co-author trailer (see note below)
git commit --amend
# Remove any "Co-authored-by: Copilot ..." line from the message

# 4. Push to your fork
git push origin fix/your-fix-name

# 5. Open the PR against Comfy-Org/ComfyUI master
gh auth switch --user cest-la-v
gh pr create \
  --repo Comfy-Org/ComfyUI \
  --base master \
  --head cest-la-v:fix/your-fix-name \
  --title "fix: <title>" \
  --body "<description>"
```

> **Multiple accounts:** see the github-pr skill for full auth switching guidance.

---

## Precautions

### 1. Remove AI co-author trailers — this is enforced by CI

Upstream runs a **"Check AI Co-Authors"** workflow
(`.github/workflows/check-ai-co-authors.yml`) on every PR. It scans all
commit messages for `Co-authored-by:` trailers from AI coding agents and
**fails the check** if any are found. The list includes GitHub Copilot
(`Co-authored-by:.*\bCopilot\b`), Claude, Cursor, Codex, Devin, Gemini,
Aider, Cline, Windsurf, and others.

**Every commit authored with Copilot CLI in this fork will have this trailer**
and will fail upstream CI. You must remove it before pushing to a PR branch.

```bash
# Scriptable: strip the trailer without opening an editor
git log -1 --format="%B" | grep -v "^Co-authored-by:" | sed 's/[[:space:]]*$//' \
  | python3 -c "import sys; print(sys.stdin.read().rstrip())" > /tmp/new_msg.txt
git commit --amend -F /tmp/new_msg.txt

# Or interactively
git rebase -i upstream/master
# Mark each commit as 'reword' and delete the Co-authored-by line
```

To verify no trailers remain before pushing:
```bash
git log upstream/master..HEAD --format='%B' | grep -i "co-authored-by" || echo "clean"
```

### 2. Check for upstream duplicates first

The bug may have already been reported, patched, or is in-flight upstream.
Before submitting:

```bash
gh search prs --repo Comfy-Org/ComfyUI "<keyword>" --state all
gh search issues --repo Comfy-Org/ComfyUI "<keyword>" --state all
```

### 3. Branch off `upstream/master`, not `dev`

Your `dev` branch carries fork-specific commits (generation metadata pipeline,
`.get()` safety fix, etc.). Always start your PR branch from a clean
`upstream/master` base so only the intended change is in the diff.

```bash
# Good
git checkout -b fix/foo upstream/master

# Bad — leaks fork-specific commits into the PR
git checkout -b fix/foo dev
```

### 4. Run upstream CI checks locally before pushing

Upstream runs Ruff linting and unit tests on all PRs:

```bash
ruff check .                          # must be clean
python -m pytest tests-unit/ -x       # must pass
```

If the commit touches `comfy_api_nodes/`, also run:
```bash
pylint comfy_api_nodes
```

### 5. Keep the PR minimal

The upstream project prefers small, focused changes. If your fork commit
bundles a bug fix with fork-specific additions (e.g. metadata pipeline wiring),
extract only the upstream-relevant portion into the PR branch.

---

## Fork-specific commits — do NOT upstream these

The following commits exist solely to support fork-specific features and should
never be submitted upstream:

| Commit topic | Reason |
|---|---|
| Generation metadata pipeline (`comfy_execution/generation_context.py`) | Fork-only feature |
| `SaveImage` GENERATION_METADATA hidden input | Depends on generation context |
| `revert: remove GENERATION_METADATA from vanilla SaveImage` | Fork management |
| Any `files-api` recursive scan that leaks internal paths | Review first |

---

## Upstream CI checks that will run on your PR

| Workflow | What it checks |
|---|---|
| **Check AI Co-Authors** | No Copilot/Claude/etc. `Co-authored-by` trailers |
| **Python Linting** | `ruff check .` passes |
| **Unit Tests** | `pytest tests-unit/` passes |
| **Execution Tests** | End-to-end execution tests pass |
| **Check for Windows Line Endings** | No CRLF in committed files |
| **Pull Request CI Workflow Runs** | Full CI suite triggered on PR |

All of these must be green before a maintainer will review.
