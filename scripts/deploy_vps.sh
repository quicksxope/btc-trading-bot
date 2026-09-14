#!/usr/bin/env bash
# Deploy project to agnostic-backtest-bot1 (no git on VPS).
set -euo pipefail

ZONE="${GCP_ZONE:-asia-southeast2-b}"
INSTANCE="${GCP_INSTANCE:-agnostic-backtest-bot1}"
PROJECT="${GCP_PROJECT:-project-f4beb162-04c9-458d-93d}"
REMOTE_DIR="${REMOTE_DIR:-/home/user/agnostic-trading-backtest}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE="${TMPDIR:-/tmp}/agbt.tgz"

echo "Packaging from $ROOT ..."
export COPYFILE_DISABLE=1
tar -C "$ROOT" \
  --exclude='.venv' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='*.pyc' \
  --exclude='._*' \
  --exclude='.DS_Store' \
  -czf "$ARCHIVE" .

echo "Uploading to $INSTANCE ..."
gcloud compute scp "$ARCHIVE" "${INSTANCE}:/tmp/agbt.tgz" --zone "$ZONE" --project "$PROJECT"

echo "Extracting and restarting services ..."
gcloud compute ssh "$INSTANCE" --zone "$ZONE" --project "$PROJECT" --command "
  set -e
  cd '$REMOTE_DIR'
  tar xzf /tmp/agbt.tgz
  find configs -name '._*' -delete 2>/dev/null || true
  sudo systemctl restart backtest-bot backtest-worker
  sleep 2
  systemctl is-active backtest-bot backtest-worker
"

echo "Done."
