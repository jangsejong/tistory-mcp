#!/usr/bin/env bash
# Development setup from a clone: venv + dependencies + login browser + checks.
# Usage:  bash scripts/setup.sh [--no-browser]
#   --no-browser : skip the Chromium download (~300MB). Run `.venv/bin/tistory-mcp install-browser`
#                  later if the login tool is needed (an installed Chrome/Edge also works).
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-python3}"

echo "==> 프로젝트: $ROOT"

if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "!! Python 3.11 이상이 필요합니다. 현재: $("$PY" --version 2>&1)" >&2
  echo "   다른 인터프리터를 쓰려면: PYTHON=python3.12 bash scripts/setup.sh" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "==> venv 생성"
  "$PY" -m venv .venv
fi

echo "==> 의존성 설치"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"

if [ "${1:-}" != "--no-browser" ]; then
  echo "==> 로그인용 Chromium 설치 (최초 1회, 약 300MB)"
  .venv/bin/tistory-mcp install-browser
else
  echo "==> Chromium 설치 건너뜀 (--no-browser)"
fi

echo "==> 검증"
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/pytest -q

BIN="$ROOT/.venv/bin/tistory-mcp"
cat <<MSG

설치 완료.

1) Claude Code 에 등록 (이 머신의 절대경로가 들어갑니다):
     claude mcp add tistory -- $BIN
   (소스 수정 없이 쓰기만 할 거라면 clone 대신 `claude mcp add tistory -- uvx tistory-mcp`)

2) 새 Claude Code 세션을 연 뒤, 블로그를 연결하세요:
     "내 티스토리 블로그 <이름>.tistory.com 연결해줘"
   브라우저 창이 뜨면 카카오 로그인 + 카카오톡 푸시 승인을 직접 하시면 됩니다.
   (터미널에서 하려면: $BIN login <이름>.tistory.com)

세션 쿠키는 이 머신의 ~/.config/tistory-mcp/sessions/ 에만 0600 으로 저장됩니다.
MSG
