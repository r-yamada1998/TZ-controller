#!/usr/bin/env bash
set -euxo pipefail

# 壊れている Yarn repo を無効化
sudo rm -f /etc/apt/sources.list.d/yarn.list
sudo rm -f /etc/apt/sources.list.d/yarn.sources

sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    pkg-config \
    libc6-dev

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

export PATH="$HOME/.local/bin:$PATH"

uv python install 3.11
uv venv --python 3.11
uv sync