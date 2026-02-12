#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/sync_upstream_openclaw.sh [--target-branch main] [--upstream-branch main] [--sync-branch-prefix sync/upstream]

Description:
  Sync official openclaw/openclaw changes into your runtime repository safely:
  - Update local target branch from origin with fast-forward only
  - Create a sync branch
  - Merge upstream branch into the sync branch

  After script finishes, push the sync branch and open a PR to target branch.

Example:
  scripts/sync_upstream_openclaw.sh
EOF
}

TARGET_BRANCH="main"
UPSTREAM_BRANCH="main"
SYNC_PREFIX="sync/upstream"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-branch)
      TARGET_BRANCH="${2:-}"
      shift 2
      ;;
    --upstream-branch)
      UPSTREAM_BRANCH="${2:-}"
      shift 2
      ;;
    --sync-branch-prefix)
      SYNC_PREFIX="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

git rev-parse --is-inside-work-tree >/dev/null

if ! git remote get-url upstream >/dev/null 2>&1; then
  echo "Error: missing upstream remote. Add it first:" >&2
  echo "  git remote add upstream https://github.com/openclaw/openclaw.git" >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Error: missing origin remote." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: working tree is not clean. Commit or stash changes first." >&2
  exit 1
fi

echo "Fetching origin/upstream ..."
git fetch origin --prune
git fetch upstream --prune

echo "Checking out $TARGET_BRANCH ..."
git checkout "$TARGET_BRANCH"

echo "Fast-forwarding $TARGET_BRANCH from origin/$TARGET_BRANCH ..."
git merge --ff-only "origin/$TARGET_BRANCH"

SYNC_BRANCH="${SYNC_PREFIX}-$(date +%Y%m%d)"
if git show-ref --verify --quiet "refs/heads/$SYNC_BRANCH"; then
  SYNC_BRANCH="${SYNC_BRANCH}-$(date +%H%M%S)"
fi

echo "Creating sync branch: $SYNC_BRANCH"
git checkout -b "$SYNC_BRANCH"

echo "Merging upstream/$UPSTREAM_BRANCH into $SYNC_BRANCH ..."
git merge --no-edit "upstream/$UPSTREAM_BRANCH"

echo
echo "Sync branch created: $SYNC_BRANCH"
echo "Next steps:"
echo "  git push -u origin $SYNC_BRANCH"
echo "  open PR: $SYNC_BRANCH -> $TARGET_BRANCH"
