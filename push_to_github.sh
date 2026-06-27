#!/usr/bin/env bash
#
# Push Prism Earth (Phase 0) to GitHub.
# Run this from your own machine (it could not run in the Cowork sandbox, which
# blocks outbound access to github.com and has no access to your GitHub creds).
#
#   chmod +x push_to_github.sh
#   ./push_to_github.sh
#
# Prerequisites: git installed, and your GitHub auth set up (a credential
# helper / PAT, or `gh auth login`). The remote repo should be EMPTY; if it
# already has commits, see the note at the bottom.

set -euo pipefail
cd "$(dirname "$0")"

REMOTE_URL="https://github.com/sri-venkat-22/Prism-Earth.git"
COMMIT_MSG="Phase 0: monorepo scaffold & foundations (SRS §9, §10, §13.16, §28, §32)"

# Start from a clean repo (removes any partial .git left by the sandbox).
rm -rf .git
git init -q
git branch -M main
git add -A
git -c user.name="sri venkat reddy" \
    -c user.email="srivenkatreddy2208@gmail.com" \
    commit -q -m "$COMMIT_MSG"

git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE_URL"

echo "Pushing to $REMOTE_URL (branch: main) ..."
git push -u origin main
echo "Done. View it at https://github.com/sri-venkat-22/Prism-Earth"

# --- If the push is REJECTED because the remote already has commits ---
#   git pull --rebase origin main   # reconcile, then re-run the push
#   git push -u origin main
# Or, to overwrite the remote with this scaffold (destructive):
#   git push -u origin main --force
