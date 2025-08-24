#!/usr/bin/env bash
set -euo pipefail

# install.sh - One-stop installer with CN mirror support for pip
# Usage:
#   ./install.sh                 # default, use PyPI
#   ./install.sh --mirror tsinghua
#   ./install.sh --mirror aliyun
#   ./install.sh --mirror ustc
#   ./install.sh --mirror tencent
#   ./install.sh --dev           # include dev extras
#   ./install.sh --mirror tsinghua --dev
#   ./install.sh --help

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

MIRROR="tsinghua"
WITH_DEV=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--mirror)
      MIRROR="${2:-pypi}"; shift 2;;
    -d|--dev)
      WITH_DEV=1; shift;;
    -h|--help)
      echo "Usage: $0 [--mirror pypi|tsinghua|aliyun|ustc|tencent] [--dev]";
      exit 0;;
    *) echo "Unknown option: $1"; exit 2;;
  esac
done

# Resolve python and pip
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
if ! command -v "$PY" >/dev/null 2>&1; then echo "python not found"; exit 1; fi

# Ensure pip present and up-to-date
"$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$PY" -m pip install -U pip setuptools wheel >/dev/null 2>&1 || true

# Use project-local pip.conf if present
export PIP_CONFIG_FILE="$ROOT_DIR/pip.conf"
echo "Using PIP_CONFIG_FILE=$PIP_CONFIG_FILE"

# Map mirror -> index URL
INDEX_URL="https://pypi.org/simple"
TRUST_HOST=""
case "$MIRROR" in
  tsinghua)
    INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple";
    TRUST_HOST="pypi.tuna.tsinghua.edu.cn";;
  aliyun)
    INDEX_URL="https://mirrors.aliyun.com/pypi/simple/";
    TRUST_HOST="mirrors.aliyun.com";;
  ustc)
    INDEX_URL="https://pypi.mirrors.ustc.edu.cn/simple/";
    TRUST_HOST="pypi.mirrors.ustc.edu.cn";;
  tencent)
    INDEX_URL="https://mirrors.cloud.tencent.com/pypi/simple";
    TRUST_HOST="mirrors.cloud.tencent.com";;
  pypi|*)
    INDEX_URL="https://pypi.org/simple";;
esac

PIP_ARGS=("--index-url" "$INDEX_URL")
if [[ -n "$TRUST_HOST" ]]; then
  PIP_ARGS+=("--trusted-host" "$TRUST_HOST")
fi

# Install project
if [[ $WITH_DEV -eq 1 ]]; then
  "$PY" -m pip install -e .[dev] "${PIP_ARGS[@]}"
else
  "$PY" -m pip install -e . "${PIP_ARGS[@]}"
fi

echo "Install finished using mirror: $MIRROR -> $INDEX_URL"
