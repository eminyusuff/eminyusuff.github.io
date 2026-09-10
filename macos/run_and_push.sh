#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# Keep the local clone current before generating data.
git pull --rebase --autostash origin main

/usr/bin/python3 "$REPO_DIR/macos/sync_apple_academic.py"

git add data/apple_inbox.json assets/events 2>/dev/null || true

if git diff --cached --quiet; then
  echo "$(date): No Apple Calendar/Reminders changes."
  exit 0
fi

git commit -m "chore: sync Apple Calendar and Reminders"

# A remote workflow may have committed meanwhile; rebase once before pushing.
if ! git push origin main; then
  git pull --rebase --autostash origin main
  git push origin main
fi

echo "$(date): Academic website Apple sync complete."
