<!-- mcp-name: io.github.jangsejong/tistory-mcp -->
<h1 align="center">tistory-mcp</h1>

<p align="center"><b>티스토리(Tistory) 블로그를 위한 AI 글쓰기 보조 MCP 서버 — Claude Code·Cursor 같은 MCP 클라이언트에서 내 블로그 글을 읽고, 쓰고, 다듬습니다. 공개 여부는 사람이 결정합니다.</b></p>
<p align="center"><i>An unofficial MCP server for Tistory blogs — an AI writing assistant where a human reviews before anything goes public.</i></p>
<p align="center"><a href="https://github.com/jangsejong/tistory-mcp/blob/main/README.en.md">English README</a></p>

[![PyPI](https://img.shields.io/pypi/v/tistory-mcp)](https://pypi.org/project/tistory-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/tistory-mcp)](https://pypi.org/project/tistory-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jangsejong/tistory-mcp/blob/main/LICENSE)
[![CI](https://github.com/jangsejong/tistory-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jangsejong/tistory-mcp/actions/workflows/ci.yml)

[<img src="https://img.shields.io/badge/VS_Code-VS_Code?style=flat-square&label=Install%20Server&color=0098FF" alt="Install in VS Code">](https://insiders.vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F%257B%2522name%2522%253A%2522tistory%2522%252C%2522command%2522%253A%2522uvx%2522%252C%2522args%2522%253A%255B%2522tistory-mcp%2522%255D%257D) [<img src="https://cursor.com/deeplink/mcp-install-dark.svg" alt="Install in Cursor">](https://cursor.com/en/install-mcp?name=tistory&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJ0aXN0b3J5LW1jcCJdfQ%3D%3D)

> **비공식 · 카카오/티스토리와 무관.** 티스토리 Open API 는 2024년 2월에 종료되었습니다. 이 프로젝트는 브라우저에서 카카오 로그인을 한 번 마친 뒤 내 PC 에 저장한 쿠키로, 티스토리 관리자 화면이 쓰는 내부 JSON API 를 호출합니다. 카카오·티스토리와 아무 관계가 없고, 티스토리 내부가 바뀌면 언제든 멈출 수 있습니다. 엔드포인트 지식은 MIT 라이선스로 공개된 [kim-se-hee/tistory-mcp](https://github.com/kim-se-hee/tistory-mcp) 의 실측 문서를 따릅니다 — 그 프로젝트는 npm 에 `tistory-mcp` 로 배포되는 **별개의 TypeScript 프로젝트**입니다. **`npx tistory-mcp` 와 `uvx tistory-mcp` 는 서로 다른 프로젝트**이며, 이 저장소는 Python/PyPI 쪽입니다.

## 왜 tistory-mcp 인가

- **글쓰기는 AI, 공개는 사람.** 발행 기본값이 **비공개**입니다. AI 가 쓴 글을 티스토리에서 직접 읽어 본 뒤 공개로 바꾸는 흐름이 기본이고, 공개 발행은 사용자가 명시적으로 요청해야 합니다.
- **내 PC 를 벗어나지 않습니다.** 로그인 쿠키는 로컬 0600 파일(또는 OS keyring)에만 저장되고, 티스토리 외 어디에도 전송되지 않습니다. 텔레메트리 없음.
- **클라이언트를 가리지 않습니다.** 표준 stdio MCP 서버라 Claude Code, Claude Desktop, Cursor, VS Code, Codex CLI, Gemini CLI 등 어디서나 같은 11개 도구를 씁니다.

## 기능

- 마크다운 → 티스토리 에디터 서식(`data-ke-*` 속성)이 붙은 HTML 변환. 제목·코드 블록·표·인용·이미지가 에디터로 쓴 글처럼 보입니다.
- 새 글 발행(비공개 기본) · 본문 수정 · 삭제 · 카테고리 조회 · 비공개 글을 포함한 목록과 본문 조회.
- 이미지 업로드 — 본문에 넣을 치환자와 첨부 참조를 함께 돌려줘 이미지가 나중에 깨지지 않게 합니다.
- 에디터 자동저장 슬롯에 초안 저장("이어서 작성"으로 복원).
- 로그인 없이 아무 티스토리 블로그의 공개 글 RSS 조회.
- 터미널 CLI(`login` / `status` / `logout`) — MCP 클라이언트의 도구 타임아웃을 피해 터미널에서 로그인.

## 안전 기본값

| 항목 | 기본 동작 | 바꾸려면 |
|---|---|---|
| 발행 공개 범위 | **비공개(private)** | 도구 호출에 `visibility="public"` 명시 |
| 삭제 | `confirm=true` 가 없으면 거부. MCP `destructiveHint` 표시 | — |
| 발행·수정 속도 | 60초 간격, 하루 20회(프로세스 안 스레드 락) | `TISTORY_MCP_MIN_INTERVAL_SEC`, `TISTORY_MCP_DAILY_CAP` (0 = 해제) |
| 발행 재시도 | 자동 재시도 없음 — `publish` 는 호출할 때마다 **새 글**을 만듭니다 | — |
| 대상 호스트 | `*.tistory.com` 만 허용 | `TISTORY_MCP_ALLOW_ANY_HOST=1` |
| 브라우저 CDP 주소 | loopback(`127.0.0.1`/`localhost`)만 허용 | `TISTORY_MCP_ALLOW_REMOTE_CDP=1` |
| 본문 HTML | [nh3](https://github.com/messense/nh3) 로 정화 — `script`·`on*` 제거, 링크 스킴은 `http`/`https`/`mailto`/`tel` 만 | — |
| 이미지 치환자 | `tistory_upload_image` 가 돌려준 형식과 정확히 일치해야 통과 | — |

## 빠른 시작 (3단계)

### 1. 설치

[uv](https://docs.astral.sh/uv/) 가 있으면 `uvx` 가 패키지를 받아 실행합니다.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

로그인 창을 띄울 브라우저가 필요합니다. **Chrome 또는 Edge 가 설치돼 있으면 이 단계는 건너뛰어도 됩니다** (로그인은 번들 Chromium → Chrome → Edge 순으로 시도).

```bash
uvx tistory-mcp install-browser   # Playwright Chromium 다운로드, 최초 1회 약 300MB
```

<details>
<summary>pipx / pip 로 설치</summary>

```bash
pipx install tistory-mcp          # 또는 가상환경에서 pip install tistory-mcp
tistory-mcp --version
```

이 경우 클라이언트 설정의 `command` 는 `uvx` 대신 `tistory-mcp` 로, `args` 는 빈 배열로 둡니다.

</details>

<details>
<summary>소스에서 (개발용)</summary>

```bash
git clone https://github.com/jangsejong/tistory-mcp.git
cd tistory-mcp
bash scripts/setup.sh             # venv + 의존성 + Chromium + ruff/pytest  (--no-browser 로 Chromium 생략)
claude mcp add tistory -- "$PWD/.venv/bin/tistory-mcp"
```

개발 보조 스크립트:

```bash
python scripts/mcp_probe.py .venv/bin/tistory-mcp                    # initialize + tools/list 핸드셰이크
python scripts/mcp_call.py  .venv/bin/tistory-mcp -- tistory_fetch_public_posts '{"blog_url":"example.tistory.com","limit":3}'
python scripts/mcp_call.py  .venv/bin/tistory-mcp -- tistory_publish_post @args.json   # 긴 본문은 @파일
```

</details>

### 2. 클라이언트에 등록

Claude Code 예시(다른 클라이언트는 [아래](#클라이언트별-설정)):

```bash
claude mcp add tistory --scope user -- uvx tistory-mcp
```

### 3. 블로그 연결

새 세션을 열고 AI 에게 말합니다.

> 내 티스토리 블로그 myblog.tistory.com 연결해줘

브라우저 창이 뜨면 **카카오 로그인 → 카카오톡 푸시 승인**을 직접 마칩니다. 쿠키가 저장되면 끝입니다. 이후에는 세션이 만료될 때까지 브라우저 없이 동작합니다. 세션 수명은 넉넉하지 않습니다 — 실측(2026-10-27)에서는 로그인 뒤 한 시간 남짓 지나자 만료된 적이 있습니다. 만료되면 도구가 알려 주므로 다시 로그인하면 됩니다.

바로 써 볼 만한 요청:

> `./post.md` 를 '개발' 카테고리에 **비공개로** 올려줘. 태그는 python, mcp.

## 클라이언트별 설정

대부분의 클라이언트는 아래 한 줄이면 됩니다. 환경변수는 각 클라이언트의 `env` 항목으로 넘깁니다.

```json
{"mcpServers":{"tistory":{"command":"uvx","args":["tistory-mcp"]}}}
```

<details>
<summary>Claude Code</summary>

```bash
claude mcp add tistory --scope user -- uvx tistory-mcp
claude mcp list        # 확인
claude mcp remove tistory
```

`--scope user` 는 모든 프로젝트에서, 생략(`local`)하면 현재 프로젝트에서만 보입니다. 프로젝트에 `.mcp.json` 을 두는 `project` 범위도 있습니다(이 저장소의 `.mcp.json.example` 참고).

플러그인으로 설치할 수도 있습니다(같은 `uvx tistory-mcp` 를 등록):

```text
/plugin marketplace add jangsejong/tistory-mcp
/plugin install tistory@tistory-mcp
``` 로그인 도구가 도중에 끊기면 서버 항목에 `"timeout"`(밀리초)을 주거나 `MCP_TOOL_TIMEOUT` 환경변수를 늘리고, 그래도 안 되면 터미널에서 `tistory-mcp login` 을 쓰세요.

</details>

<details>
<summary>Claude Desktop</summary>

설정 파일(Claude 메뉴 → Settings → Developer → Edit Config):

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tistory": {
      "command": "uvx",
      "args": ["tistory-mcp"]
    }
  }
}
```

저장 후 Claude Desktop 을 완전히 종료했다가 다시 엽니다. macOS 의 GUI 앱은 셸의 `PATH`(`~/.local/bin` 등)를 못 볼 수 있으니 서버가 뜨지 않으면 `command` 에 `which uvx` 결과(절대경로)를 넣으세요.

</details>

<details>
<summary>Cursor</summary>

전역 `~/.cursor/mcp.json` 또는 프로젝트 `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "tistory": {
      "command": "uvx",
      "args": ["tistory-mcp"]
    }
  }
}
```

위의 "Install in Cursor" 버튼을 눌러도 같은 설정이 들어갑니다.

</details>

<details>
<summary>VS Code (Copilot)</summary>

워크스페이스 `.vscode/mcp.json` (VS Code 는 `mcpServers` 가 아니라 `servers` 키를 씁니다):

```json
{
  "servers": {
    "tistory": {
      "type": "stdio",
      "command": "uvx",
      "args": ["tistory-mcp"]
    }
  }
}
```

사용자 프로필에 두려면 명령 팔레트에서 **MCP: Open User Configuration** 으로 `mcp.json` 을 열어 같은 내용을 넣거나, 터미널에서 `code --add-mcp '{"name":"tistory","type":"stdio","command":"uvx","args":["tistory-mcp"]}'` 를 실행합니다. 위의 "Install in VS Code" 버튼도 같은 일을 합니다.

</details>

<details>
<summary>Codex CLI</summary>

```bash
codex mcp add tistory -- uvx tistory-mcp
```

또는 `~/.codex/config.toml`:

```toml
[mcp_servers.tistory]
command = "uvx"
args = ["tistory-mcp"]
```

Codex 의 도구 호출 제한(`tool_timeout_sec`)은 기본 60초라 브라우저 로그인이 그 안에 끝나기 어렵습니다. 같은 테이블에 `tool_timeout_sec = 600` 을 두거나, 터미널에서 `tistory-mcp login myblog.tistory.com` 으로 먼저 로그인해 두세요.

</details>

<details>
<summary>Gemini CLI</summary>

```bash
gemini mcp add -s user tistory uvx tistory-mcp
```

또는 `~/.gemini/settings.json` (프로젝트는 `.gemini/settings.json`):

```json
{
  "mcpServers": {
    "tistory": {
      "command": "uvx",
      "args": ["tistory-mcp"]
    }
  }
}
```

</details>

그 밖의 클라이언트는 위의 공통 JSON(`mcpServers` 형식)을 해당 클라이언트의 MCP 설정 파일에 넣으면 됩니다.

## 첫 로그인

`tistory_session_init` 도구(또는 AI 에게 "블로그 연결해줘")가 브라우저 창을 띄웁니다. 카카오 로그인과 카카오톡 푸시 승인은 **사용자가 직접** 합니다 — 이 2단계 인증은 자동화할 수 없고, 그래서 완전 무인 운영은 설계상 불가능합니다. 로그인이 끝나면 쿠키만 저장되고 창은 닫힙니다.

창이 안 뜨거나 클라이언트가 기다려 주지 않을 때의 대안 세 가지:

**1) 터미널에서 로그인(권장)** — MCP 클라이언트의 도구 타임아웃과 무관하게 최대 5분(`--timeout`)을 기다립니다.

```bash
tistory-mcp login myblog.tistory.com          # uvx 사용 시: uvx tistory-mcp login myblog.tistory.com
tistory-mcp status myblog.tistory.com         # 저장된 세션과 유효 여부
tistory-mcp logout myblog.tistory.com         # 세션 삭제
```

**2) 이미 떠 있는 브라우저에 붙기 (WSL · SSH · 컨테이너 등 화면이 없는 환경)** — 화면이 있는 쪽(예: Windows 데스크톱)에서 원격 디버깅 포트를 열고 브라우저를 띄운 뒤, 서버에는 그 주소만 알려 줍니다.

```bat
:: Windows 데스크톱 — Edge 또는 Chrome
msedge --remote-debugging-port=9222 --user-data-dir=%TEMP%\tistory-login
chrome --remote-debugging-port=9222 --user-data-dir=%TEMP%\tistory-login
```

```bash
# WSL 등 서버 쪽
tistory-mcp login myblog.tistory.com --cdp-url http://127.0.0.1:9222
# 도구로 할 때는 cdp_url="http://127.0.0.1:9222", 또는 환경변수 TISTORY_MCP_CDP_URL
```

붙은 브라우저의 쿠키를 읽어 오므로, 평소 쓰는 프로필 대신 **전용 `--user-data-dir`** 를 쓰는 것을 권합니다. CDP 주소는 기본적으로 loopback 만 허용됩니다.

**3) 원격 서버** — 로컬 PC 에서 2) 처럼 브라우저를 띄운 뒤, 로컬 PC 에서 서버로 접속하면서 서버 쪽 포트를 내 브라우저로 **역방향** 포워딩합니다. 서버에서는 여전히 `127.0.0.1:9222` 로 보이므로 원격 허용 설정이 필요 없습니다.

```bash
ssh -R 9222:127.0.0.1:9222 user@server     # 로컬 PC 에서 실행 — 서버의 127.0.0.1:9222 → 내 브라우저
```

## 도구

| 도구 | 종류 | 설명 | 로그인 |
|---|---|---|---|
| `tistory_session_init` | 쓰기 | 브라우저를 열어 카카오 로그인 → 쿠키 저장. `cdp_url` 을 주면 `--remote-debugging-port=9222` 로 떠 있는 브라우저에 붙음(WSL·SSH·컨테이너용) | 이 도구가 로그인 |
| `tistory_session_status` | 읽기 | 저장된 세션 유무·저장 시각·만료 예정, 그리고 지금 유효한지(관리자 API 1회 호출) | 불필요 |
| `tistory_get_categories` | 읽기 | 카테고리 트리(정수 id). 발행·수정의 `category` 는 이름이 아니라 이 id | 필요 |
| `tistory_list_posts` | 읽기 | 관리자 글 목록(비공개·보호 글 포함). 키워드·검색 범위·공개 범위·카테고리·페이지 | 필요 |
| `tistory_get_post` | 읽기 | 글 메타 + 스킨으로 렌더된 본문 HTML. 비공개 글도 읽음 | 필요 |
| `tistory_fetch_public_posts` | 읽기 | 아무 블로그의 공개 글 RSS(최대 50건, 본문 포함 옵션) | **불필요** |
| `tistory_publish_post` | 쓰기 | **새 글** 발행. 마크다운 → 에디터 서식 HTML. 기본 **비공개**. 속도 제한. 오류 뒤 자동 재시도 금지(항상 새 글이 생김) | 필요 |
| `tistory_update_post` | 쓰기 | 본문 **전체** 교체. 제목·카테고리·공개 범위·슬러그·태그는 생략하면 유지. `content_format` 기본 `html`(마크다운이면 명시) | 필요 |
| `tistory_delete_post` | 파괴적 | 영구 삭제. `confirm=true` 필수 | 필요 |
| `tistory_upload_image` | 쓰기 | 이미지(png/jpg/gif/webp, 20MB) 업로드 → `substitution`(본문에 그대로 붙여넣기) + `attachment_ref`(`attachments` 에 전달하지 않으면 약 15일 뒤 이미지가 깨짐) | 필요 |
| `tistory_save_draft` | 쓰기 | 에디터 **자동저장 슬롯(1개)** 에 초안 기록 — 다음에 글쓰기를 열면 "이어서 작성"으로 복원. "임시저장 N개" 목록이 아니며 다시 저장하면 덮어씀 | 필요 |

도구 설명은 영문과 한국어를 병기해 어느 언어로 대화해도 같은 안내를 받습니다.

## 이런 식으로 써보세요

```text
myblog.tistory.com 카테고리 보여줘
```

```text
./post.md 를 '개발' 카테고리에 비공개로 올려줘. 태그는 python, mcp
```

```text
./diagram.png 올려서 두 번째 문단 뒤에 넣고, 비공개로 발행해줘
```

```text
검토했어. 방금 올린 글 공개로 바꿔줘
```

```text
제목에 '회고' 들어간 글 찾아서 오타만 고쳐줘. 공개 상태는 그대로
```

```text
example.tistory.com 최근 글 5개 요약해줘        (남의 블로그 공개 글 — 로그인 불필요)
```

```text
이 내용은 초안으로만 저장해 둬. 발행은 하지 말고
```

```text
내 블로그 세션 아직 살아 있어?
```

## 발행 워크플로

AI 가 쓰고 사람이 검토한 뒤 공개하는 기본 흐름입니다.

1. `tistory_get_categories` — 카테고리 **id** 를 얻습니다(이름은 받지 않음).
2. `tistory_upload_image` — 이미지마다 호출해 `substitution` 은 본문에, `attachment_ref` 는 `attachments` 목록에 넣습니다.
3. `tistory_publish_post` — 마크다운 본문으로 **비공개** 발행. 응답의 글 번호를 기억합니다.
4. 티스토리 관리자 화면에서 글을 읽어 봅니다. 고칠 게 있으면 AI 에게 말해 `tistory_update_post` 로 본문을 다시 보냅니다(마크다운이면 `content_format="markdown"`).
5. 마음에 들면 `tistory_update_post` 에 `visibility="public"` — 이때 비로소 공개됩니다.

발행이 오류나 타임아웃으로 끝났다면 바로 다시 호출하지 말고 `tistory_list_posts` 로 글이 생겼는지 먼저 확인하세요. 서버는 호출마다 새 글을 만듭니다.

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `TISTORY_MCP_HOME` | `~/.config/tistory-mcp` | 세션·속도 제한 상태 파일 위치. `XDG_CONFIG_HOME` 을 따름 |
| `TISTORY_MCP_SESSION_STORE` | `file` | `file`(0600 JSON) 또는 `keyring`(OS 자격증명 저장소). keyring 은 `pip install "tistory-mcp[keyring]"` 필요, Linux 는 Secret Service 필요, Windows 는 미지원 |
| `TISTORY_MCP_MIN_INTERVAL_SEC` | `60` | 발행·수정 사이 최소 간격(초). `0` = 해제 |
| `TISTORY_MCP_DAILY_CAP` | `20` | 하루 발행·수정 상한. `0` = 해제 |
| `TISTORY_MCP_ALLOW_ANY_HOST` | (없음) | `1` 이면 `*.tistory.com` 외 호스트(커스텀 도메인) 허용 |
| `TISTORY_MCP_CDP_URL` | (없음) | `cdp_url` 인자를 생략했을 때 쓸 브라우저 CDP 주소 |
| `TISTORY_MCP_ALLOW_REMOTE_CDP` | (없음) | `1` 이면 loopback 이 아닌 CDP 주소 허용 |
| `TISTORY_MCP_LOG_LEVEL` | `INFO` | stderr 로그 레벨 |

클라이언트 설정의 `env` 로 넘긴 값은 클라이언트를 다시 시작해야 반영됩니다.

**세션 파일 위치** (`file` 저장소, 권한 0600):

| OS | 경로 |
|---|---|
| Linux / macOS | `~/.config/tistory-mcp/sessions/myblog.tistory.com.json` (`XDG_CONFIG_HOME` 설정 시 그 아래) |
| Windows | `C:\Users\<you>\.config\tistory-mcp\sessions\myblog.tistory.com.json` |
| keyring | 서비스 `tistory-mcp`, 계정 = 블로그 호스트 |

같은 디렉터리의 `ratelimit.json` 이 속도 제한 상태입니다.

## 검증 현황

<!-- verification-table -->
| 도구 | 실제 블로그 검증 | 비고 |
|---|---|---|
| `tistory_session_init` | 완료 | |
| `tistory_session_status` | 완료 | |
| `tistory_get_categories` | 완료 | |
| `tistory_list_posts` | 완료 | |
| `tistory_get_post` | 완료 | |
| `tistory_update_post` | 완료 | |
| `tistory_fetch_public_posts` | 완료 | |
| `tistory_publish_post` | 완료 | 비공개 발행 → 공개 페이지에서 에디터 서식 속성 유지 확인 |
| `tistory_delete_post` | 완료 | |
| `tistory_upload_image` | 완료 | 업로드 → 치환자 검증 통과 → 이미지 포함 발행 → 렌더 확인 |
| `tistory_save_draft` | 완료 | 자동저장 슬롯 되읽기로 확인 |

11개 도구 모두 실제 블로그에서 확인했습니다(2026-10-27, 비공개 테스트 글로 검증 뒤 삭제). 티스토리 쪽 변경으로 동작이 달라지면 [이슈](https://github.com/jangsejong/tistory-mcp/issues)로 알려 주세요(쿠키·세션 파일은 첨부하지 마세요).

## 문제 해결 / FAQ

더 자세한 내용은 [docs/TROUBLESHOOTING.md](https://github.com/jangsejong/tistory-mcp/blob/main/docs/TROUBLESHOOTING.md).

- **"세션이 만료되었습니다"** — 로그인 세션 쿠키(`TSSESSION`)는 만료일이 없는 세션 쿠키라 서버 쪽에서 끊기며, 실측에서는 한 시간 남짓 만에 만료되기도 했습니다. `tistory_session_init` 을 다시 실행하거나 터미널에서 `tistory-mcp login myblog.tistory.com`.
- **`Executable doesn't exist` / 브라우저를 찾지 못함** — `tistory-mcp install-browser` 로 Chromium 을 받거나 Chrome/Edge 를 설치하세요. 로그인은 번들 Chromium → Chrome → Edge 순으로 시도합니다.
- **로그인 창이 안 보임 (WSL · SSH · 컨테이너)** — 화면이 있는 쪽에서 `--remote-debugging-port=9222` 로 브라우저를 띄우고 `cdp_url` 로 붙으세요. [첫 로그인](#첫-로그인) 참고.
- **로그인 중 클라이언트가 타임아웃** — 터미널에서 `tistory-mcp login myblog.tistory.com` 으로 먼저 로그인해 두면 도구는 저장된 쿠키만 씁니다. Codex CLI 는 `tool_timeout_sec`, Claude Code 는 서버 항목의 `timeout` 으로 제한을 늘릴 수도 있습니다.
- **커스텀 도메인 블로그** — `blog_url` 은 원래 주소 `myblog.tistory.com` 을 권장합니다. 커스텀 도메인을 그대로 써야 하면 `TISTORY_MCP_ALLOW_ANY_HOST=1`.
- **"간격 제한" / "일일 상한" 오류** — 기본 60초·20회/일 입니다. `TISTORY_MCP_MIN_INTERVAL_SEC`, `TISTORY_MCP_DAILY_CAP` 으로 조정(0 = 해제). 상한은 발행·수정 합산이며 `TISTORY_MCP_HOME/ratelimit.json` 에 기록됩니다.
- **이미지가 15일쯤 뒤에 깨짐** — 발행·수정 때 `attachments` 에 `attachment_ref` 를 넣지 않은 경우입니다. 해당 글을 `tistory_update_post` 로 다시 보내면서 `attachments` 를 채우세요(이미지는 다시 업로드).
- **태그 표기가 바뀜** — 이미 쓰던 태그와 대소문자·띄어쓰기만 다른 태그는 기존 표기로 합쳐지는 것으로 보입니다. 티스토리 쪽 동작입니다.
- **두 대의 PC 에서 같은 블로그에 로그인** — 동시 로그인 시 한쪽 세션이 끊기는지 확인되지 않았습니다. 한 PC 에서 쓰는 것을 권합니다.
- **`update_post` 에 마크다운을 보냈더니 기호가 그대로 보임** — `update_post` 의 `content_format` 기본값은 `html` 입니다. 마크다운이면 `content_format="markdown"` 을 명시하세요(`publish_post` 는 기본 `markdown`).
- **`get_post` 본문이 마크다운이 아님** — 티스토리는 마크다운을 저장하지 않습니다. 돌아오는 것은 스킨으로 렌더된 HTML 이며, 수정할 때는 그 HTML 을 되돌려 보내지 말고 새 본문을 써서 보내세요.

## 한계와 면책

- **비공식**입니다. 티스토리가 내부 API 를 바꾸면 예고 없이 동작이 멈출 수 있습니다.
- 이 도구의 사용은 티스토리·카카오 약관과 충돌할 수 있습니다. 계정 제한 등 **모든 위험은 사용자 본인**이 집니다.
- 완전 무인 운영은 불가능합니다(카카오톡 푸시 승인). 세션은 짧으면 한 시간 남짓 만에 만료되므로, 도구가 만료를 알리면 다시 로그인해야 합니다.
- 속도 제한은 프로세스 안에서만 직렬화됩니다. 두 클라이언트가 동시에 발행하면 간격 검사가 겹칠 수 있습니다.
- 텔레메트리·외부 서버 없음. 쿠키는 티스토리로 보내는 요청 외에는 이 PC 를 떠나지 않습니다.

### 허용하지 않는 사용

- 대량·반복 발행, 같은 글을 여러 블로그에 뿌리기, 스팸.
- 검색엔진 조작을 노린 글 양산.
- 본인 소유가 아닌 블로그·계정에 글 쓰기.
- 티스토리·카카오 약관이 금지하는 행위 전반.

이 프로젝트는 **내 블로그**를 위한 글쓰기 보조이며, 공개 전에 사람이 읽는 것을 전제로 만들었습니다.

## 보안

- 저장된 쿠키는 **블로그 관리자 권한 그 자체**입니다. 세션 파일을 복사·공유하지 마세요.
- 이슈·PR 에 쿠키, 세션 JSON, HAR, 스크린샷 속 토큰을 **절대 첨부하지 마세요**.
- 텔레메트리 없음. 네트워크 요청은 로그인한 티스토리 호스트와 RSS 조회 대상 블로그로만 나갑니다.
- 취약점 신고 절차는 [SECURITY.md](https://github.com/jangsejong/tistory-mcp/blob/main/SECURITY.md).

## 기여

버그 신고와 PR 을 환영합니다 — [CONTRIBUTING.md](https://github.com/jangsejong/tistory-mcp/blob/main/CONTRIBUTING.md). 내부 구조는 [docs/ARCHITECTURE.md](https://github.com/jangsejong/tistory-mcp/blob/main/docs/ARCHITECTURE.md). 테스트는 네트워크 없이 돕니다(`pytest`, 모의 HTTP).

## 라이선스

[MIT](https://github.com/jangsejong/tistory-mcp/blob/main/LICENSE)

## 감사

- [kim-se-hee/tistory-mcp](https://github.com/kim-se-hee/tistory-mcp) (MIT) — 티스토리 내부 엔드포인트를 실측해 정리한 `docs/api.md`. 이 저장소의 엔드포인트 지식은 그 문서를 따릅니다. npm 에 배포되는 별개의 TypeScript 프로젝트입니다.
- [aiarchitecturedev/aiarchitect-blog-mcp](https://github.com/aiarchitecturedev/aiarchitect-blog-mcp) — 도구 annotation 과 fail-closed 패턴을 참고했습니다.

## Changelog

### v0.2.0 (2026-10-27)
- 문서: 세션 수명 서술 정정 — "며칠~몇 주"가 아니라 실측 한 시간 남짓 만에 만료될 수 있음(`TSSESSION` 은 만료일 없는 세션 쿠키)

첫 공개 릴리스.

- 도구 11개 — 세션(`init`/`status`), 카테고리, 글 목록·조회, 공개 RSS, 발행·수정·삭제, 이미지 업로드, 자동저장 초안. 도구 설명·title 영문+한국어 병기.
- 안전 기본값 — 비공개 발행, 삭제 `confirm` + `destructiveHint`, 발행·수정 속도 제한(60초·하루 20회, 스레드 락), `*.tistory.com` 한정, CDP loopback 한정, nh3 본문 정화.
- 이미지 치환자 엄격 검증 — 비공개 0.1.x 에서 발견된 sanitize 우회를 수정.
- 발행 실패 뒤 재시도 시 중복 글 경고.
- 로그인 — 번들 Chromium → Chrome → Edge 순 폴백, `cdp_url` 로 외부 브라우저 접속, keyring 오류 안내.
- 배포 — PyPI `tistory-mcp`(`uvx tistory-mcp`), CLI 서브커맨드 `install-browser` / `login` / `status` / `logout` / `--version`.
- `tistory_list_posts` — 공개 범위 필터를 서버 어휘(`visible`/`hidden`/`protect`)로 매핑(다른 값은 서버가 400). `search_type` 에 `tag` 추가, 서버가 거부하는 `all` 제거.
- 실계정 검증 — 11개 도구 전부 실제 블로그에서 확인(비공개 테스트 글로 검증 뒤 삭제).
- Python ≥3.11.
- 비공개 개발 단계(v0.1.0~v0.1.4, 2026-09~10)의 이력은 이 항목으로 요약.
