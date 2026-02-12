#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/bootstrap_runtime_repo.sh --fork-url <github-fork-url> [--path <target-dir>] [--upstream-url <url>]

Description:
  Prepare a dedicated OpenClaw runtime repository for customization work.
  - Clone your fork as origin (if target dir does not exist)
  - Ensure upstream remote points to official openclaw/openclaw
  - Fetch both remotes
  - Ensure local main tracks origin/main

Examples:
  scripts/bootstrap_runtime_repo.sh \
    --fork-url https://github.com/<your-org>/openclaw-runtime.git

  scripts/bootstrap_runtime_repo.sh \
    --fork-url git@github.com:<your-org>/openclaw-runtime.git \
    --path runtime/openclaw-runtime
EOF
}

FORK_URL=""
TARGET_DIR="runtime/openclaw-runtime"
UPSTREAM_URL="https://github.com/openclaw/openclaw.git"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fork-url)
      FORK_URL="${2:-}"
      shift 2
      ;;
    --path)
      TARGET_DIR="${2:-}"
      shift 2
      ;;
    --upstream-url)
      UPSTREAM_URL="${2:-}"
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

if [[ -z "$FORK_URL" ]]; then
  echo "Error: --fork-url is required." >&2
  usage
  exit 1
fi

if [[ -d "$TARGET_DIR/.git" ]]; then
  echo "Using existing git repo: $TARGET_DIR"
else
  if [[ -e "$TARGET_DIR" ]]; then
    echo "Error: target path exists but is not a git repo: $TARGET_DIR" >&2
    exit 1
  fi
  echo "Cloning fork into $TARGET_DIR ..."
  git clone "$FORK_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"

ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
if [[ -z "$ORIGIN_URL" ]]; then
  git remote add origin "$FORK_URL"
elif [[ "$ORIGIN_URL" != "$FORK_URL" ]]; then
  echo "Updating origin remote:"
  echo "  old: $ORIGIN_URL"
  echo "  new: $FORK_URL"
  git remote set-url origin "$FORK_URL"
fi

if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream "$UPSTREAM_URL"
else
  git remote add upstream "$UPSTREAM_URL"
fi

echo "Fetching remotes ..."
git fetch origin --prune
git fetch upstream --prune

if git show-ref --verify --quiet refs/heads/main; then
  git checkout main
else
  git checkout -b main origin/main
fi

git branch --set-upstream-to=origin/main main >/dev/null 2>&1 || true

echo
echo "Runtime repo is ready."
echo "Path: $(pwd)"
echo "Remotes:"
git remote -v
echo
echo "Next steps:"
echo "  1) Create feature branch: git checkout -b feat/<your-feature>"
echo "  2) Commit + push: git push -u origin feat/<your-feature>"
echo "  3) Merge to main for Zeabur auto-deploy"
