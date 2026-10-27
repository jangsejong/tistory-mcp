# 문제 해결

증상 → 원인 → 조치 순으로 적는다. 명령은 `uvx tistory-mcp …` 기준이며, 소스를 clone 해
설치했다면 `.venv/bin/tistory-mcp …` 로 바꿔 읽는다. 블로그 주소는 `myblog.tistory.com` 으로
표기한다.

- [1. 세션·로그인](#1-세션로그인)
- [2. 설치·클라이언트 등록](#2-설치클라이언트-등록)
- [3. 호스트·설정](#3-호스트설정)
- [4. 본문·이미지·발행](#4-본문이미지발행)
- [5. 디버깅](#5-디버깅)
- [6. 이슈 제출 시](#6-이슈-제출-시)

## 1. 세션·로그인

### 1.1 "저장된 세션이 없습니다" / "쿠키가 모두 만료되었습니다" / "세션이 없거나 만료되었습니다"

- **증상**: 도구가 위 문구와 함께 `tistory_session_init` 을 안내한다. `tistory_session_status`
  가 `live: "none"` 또는 `"expired"` 를 돌려준다.
- **원인**: 아직 로그인하지 않았거나, 쿠키가 만료됐거나, 카카오 쪽 세션이 먼저 끊겼다.
  `earliest_expiry` 는 쿠키의 만료 메타데이터일 뿐 실제 수명을 보장하지 않는다(며칠~몇 주).
- **조치**: 채팅에서 `tistory_session_init` 을 부르거나 터미널에서

  ```bash
  uvx tistory-mcp login myblog.tistory.com
  uvx tistory-mcp status myblog.tistory.com     # live: "valid" 확인
  ```

  브라우저 창에서 카카오 로그인과 카카오톡 푸시 승인을 직접 마치면 `/manage` 화면이 뜨는
  순간 쿠키가 저장되고 창이 닫힌다. 세션을 지우려면 `uvx tistory-mcp logout myblog.tistory.com`.

### 1.2 `Executable doesn't exist` / "브라우저를 열지 못했습니다"

- **증상**: 로그인 도구가 `브라우저 오류: … Executable doesn't exist …` 또는
  `브라우저를 열지 못했습니다 (chromium: … / chrome: … / msedge: …)` 를 돌려준다.
- **원인**: 로그인은 번들 Chromium → Chrome → Edge 순으로 띄우는데 셋 다 없다. Playwright 는
  버전마다 정해진 Chromium 빌드를 요구하므로 `tistory-mcp` 를 올린 뒤 다시 나기도 한다.
- **조치**: 둘 중 하나.

  ```bash
  uvx tistory-mcp install-browser      # 번들 Chromium 설치 (최초 1회, 약 300MB)
  ```

  또는 Chrome/Edge 를 설치한다(이미 있으면 다운로드 없이 그걸 쓴다).

### 1.3 브라우저 창이 안 보임 (WSL·SSH·컨테이너)

- **증상**: 로그인 도구가 `N초 안에 로그인이 완료되지 않았습니다. 브라우저 창이 보이지 않는
  환경(WSL·SSH·컨테이너)이면 cdp_url 경로를 사용하세요` 로 끝난다. 창이 떴다는 흔적이 없다.
- **원인**: 서버가 도는 셸에 디스플레이가 없다(SSH 세션, 컨테이너, WSLg 가 죽은 WSL).
- **조치**: 창은 **디스플레이가 있는 데스크톱**에서 띄우고, 서버는 CDP 로 거기에 붙는다.

  1. 데스크톱에서 원격 디버깅 포트를 연 브라우저를 **전용 프로필**로 띄운다. 최근 Chrome/Edge
     는 기본 프로필에서 원격 디버깅을 막을 수 있으므로 `--user-data-dir` 는 필수다.

     ```
     # Windows (Win+R)
     msedge --remote-debugging-port=9222 --user-data-dir=%TEMP%\tistory-login
     chrome --remote-debugging-port=9222 --user-data-dir=%TEMP%\tistory-login
     # macOS
     "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir=/tmp/tistory-login
     # Linux
     google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/tistory-login
     ```

  2. 서버 쪽에서 CDP 주소를 넘긴다. 셋 중 하나.

     ```bash
     uvx tistory-mcp login myblog.tistory.com --cdp-url http://127.0.0.1:9222
     ```

     채팅이라면 `tistory_session_init(blog_url=..., cdp_url="http://127.0.0.1:9222")`, 항상 쓸
     거라면 클라이언트 설정의 `env` 에 `TISTORY_MCP_CDP_URL=http://127.0.0.1:9222`.

  3. 브라우저에 새 탭이 열리면 카카오 로그인 + 푸시 승인을 마친다. `/manage` 에 도착하면
     쿠키를 저장하고 **탭만** 닫는다(브라우저는 남는다). 끝나면 그 브라우저를 닫아도 된다 —
     전용 프로필에 로그인 상태가 남으므로 공용 PC 라면 프로필 디렉터리를 지운다.

- **WSL2**: 서버가 WSL 안에서 돌고 브라우저는 Windows 에 있다면 WSL 의 `127.0.0.1:9222` 가
  Windows 의 리스너에 닿아야 한다. 기본 NAT 모드에서는 닿지 않으므로 `%USERPROFILE%\.wslconfig`
  에 `[wsl2]` / `networkingMode=mirrored` 를 넣고 `wsl --shutdown` 뒤 다시 연다
  (mirrored 네트워킹은 loopback 을 양쪽이 공유한다).
- **원격 서버**: 서버가 SSH 너머에 있다면 데스크톱에서 접속할 때 **remote forward** 로 서버의
  9222 를 데스크톱 브라우저로 넘긴다.

  ```bash
  ssh -R 9222:127.0.0.1:9222 user@server      # 서버의 127.0.0.1:9222 → 데스크톱 브라우저
  ```

  그러면 서버 쪽에서는 그대로 `cdp_url=http://127.0.0.1:9222` 를 쓴다.
- `cdp_url 은 기본적으로 localhost/127.0.0.1 만 허용합니다` 가 나오면 원격 주소를 직접 넣은
  것이다. 위처럼 터널로 loopback 에 가져오는 쪽을 권한다. 정말 원격 주소가 필요하면
  `TISTORY_MCP_ALLOW_REMOTE_CDP=1` 이지만, 그 브라우저에 로그인 쿠키가 남는다는 점을 감수해야
  한다.

### 1.4 로그인 중 클라이언트가 타임아웃

- **증상**: 브라우저 창은 떴는데 클라이언트가 먼저 "도구 호출 시간 초과"를 내고, 로그인을
  마쳐도 세션이 저장돼 있지 않다.
- **원인**: `tistory_session_init` 은 사람이 로그인을 끝낼 때까지(최대 `timeout_sec`, 기본
  300초) 블로킹된다. 일부 클라이언트는 그보다 먼저 호출을 끊고, 끊긴 호출의 결과는
  저장되지 않을 수 있다.
- **조치**: 터미널에서 로그인한다. 세션 파일을 같이 쓰므로 서버를 재시작하지 않아도 다음 도구
  호출부터 바로 동작한다.

  ```bash
  uvx tistory-mcp login myblog.tistory.com --timeout 600
  ```

  클라이언트 쪽 도구 타임아웃을 늘릴 수도 있다(예: Codex CLI 의 `tool_timeout_sec`, Claude Code
  의 서버 항목 `timeout` 또는 `MCP_TOOL_TIMEOUT` — README 의 클라이언트별 설정 참고).

### 1.5 "로그인은 끝났지만 블로그 도메인 쿠키를 찾지 못했습니다"

- **원인**: `/manage` 에는 도착했는데 컨텍스트의 쿠키 중 블로그 호스트에 매칭되는 것이 없다.
  CDP 경로에서 다른 컨텍스트·프로필에 로그인했거나, 주소를 잘못 넣은 경우가 대부분이다.
- **조치**: `blog_url` 이 로그인한 블로그와 같은지 확인하고, CDP 경로라면 서버가 연 탭에서
  로그인했는지 확인한다.

### 1.6 두 머신에서 같은 블로그에 로그인

- 두 번째 머신의 로그인이 첫 번째 세션을 무효화하는지는 **확인되지 않았다.** 각 머신에서
  따로 `login` 하고, 만료되면 그 머신에서 다시 로그인한다. 세션 파일을 다른 머신으로 복사하는
  것은 권하지 않는다(쿠키 = 블로그 관리 권한 전부).

## 2. 설치·클라이언트 등록

### 2.1 macOS GUI 앱이 `uvx` 를 못 찾음

- **증상**: Claude Desktop 같은 GUI 앱에서 서버가 "command not found" 로 뜨지 않는다. 터미널에서는
  `uvx tistory-mcp --version` 이 되는데도.
- **원인**: GUI 앱은 셸의 `PATH` 를 상속하지 않는다.
- **조치**: `which uvx` 로 얻은 절대경로를 `command` 에 넣는다.

  ```json
  { "mcpServers": { "tistory": { "command": "/opt/homebrew/bin/uvx", "args": ["tistory-mcp"] } } }
  ```

  (`~/.local/bin/uvx` 처럼 홈 아래에 있으면 `~` 를 풀어 쓴 실제 절대경로를 넣는다.)

### 2.2 도구 목록이 비어 있음 / 서버가 바로 종료됨

- **조치**: 클라이언트 밖에서 먼저 확인한다.

  ```bash
  uvx tistory-mcp --version                       # 0.2.0 처럼 버전이 나와야 함 (Python ≥ 3.11)
  python scripts/mcp_probe.py uvx tistory-mcp     # initialize + tools/list → "PROBE OK", 도구 11개
  ```

  probe 가 `[stdout 비JSON] …` 줄을 찍으면 무언가가 stdout 에 글을 쓰고 있는 것이다(래퍼
  스크립트의 `echo`, 셸 초기화 파일의 출력 등). stdout 은 JSON-RPC 채널이라 한 줄만 섞여도
  클라이언트가 파싱 오류를 낸다. 로그·안내는 stderr 로 보낸다.

### 2.3 Windows 에서 세션 파일 위치

- 기본 경로는 `%USERPROFILE%\.config\tistory-mcp\sessions\<host>.json` 이다
  (`XDG_CONFIG_HOME` 또는 `TISTORY_MCP_HOME` 이 있으면 그 아래). 로그인 결과의 `stored_at` 에
  실제 경로가 나온다.
- Windows 에는 POSIX 0600 권한이 없다. 파일은 사용자 프로필의 ACL 로만 보호되므로 공용 계정에서는
  `TISTORY_MCP_HOME` 을 본인만 접근 가능한 위치로 두고, 다 쓰면 `logout` 으로 지운다.

### 2.4 keyring 오류

| 메시지 | 원인 | 조치 |
|--------|------|------|
| `keyring 패키지가 없습니다` | `TISTORY_MCP_SESSION_STORE=keyring` 인데 패키지 미설치 | `pip install "tistory-mcp[keyring]"` 또는 `uvx --with keyring tistory-mcp` |
| `keyring 저장 실패: …` / `keyring 조회 실패: …` | OS 자격증명 저장소에 못 붙음 — 헤드리스 Linux·WSL 에 Secret Service(D-Bus) 가 없는 경우가 대부분 | 파일 저장소로 돌아간다: `TISTORY_MCP_SESSION_STORE` 를 비운다(기본값 `file`) |

파일 저장소와 keyring 은 세션을 공유하지 않는다. 백엔드를 바꾸면 다시 로그인한다.
keyring 은 macOS Keychain · Linux Secret Service 만 안내 대상이며 Windows 는 지원하지 않는다.

## 3. 호스트·설정

### 3.1 커스텀 도메인: "… 은(는) *.tistory.com 이 아닙니다"

- **원인**: 호스트 allowlist 가 `*.tistory.com` 만 허용한다(SSRF·오발행 방지).
- **조치**: 커스텀 도메인을 연결한 블로그도 원래 주소 `myblog.tistory.com` 으로 관리자 API 를
  쓸 수 있으므로 **원래 주소 사용을 권한다.** 꼭 커스텀 도메인으로 써야 하면 클라이언트 설정
  `env` 에 `TISTORY_MCP_ALLOW_ANY_HOST=1`. 이 경로는 검증되지 않았다 — 발행 응답의 `entryUrl`
  호스트가 요청 호스트와 다르면 `entryUrl 의 host 가 대상 블로그와 다릅니다` 로 실패할 수 있다.

### 3.2 rate limit

- **증상**: `publish 간격 제한: N초 후 다시 시도하세요 (TISTORY_MCP_MIN_INTERVAL_SEC=60)` 또는
  `update 일일 상한 20건 도달 (TISTORY_MCP_DAILY_CAP). 내일 다시 시도하세요`.
- **원인**: 발행과 수정을 합쳐 최소 60초 간격, 하루 20건으로 제한한다(대량 발행에 따른 계정
  제재 위험을 줄이는 사용자 보호 장치). 기록은 요청 직전에 남으므로 티스토리 쪽 오류로 실패한
  발행도 슬롯을 하나 쓴다. 세션 없음·호스트 거부처럼 요청 전에 실패한 호출은 쓰지 않는다.
- **조치**: 기다리거나 클라이언트 설정 `env` 로 조정한다. `0` 은 해당 제한 해제.

  ```
  TISTORY_MCP_MIN_INTERVAL_SEC=30
  TISTORY_MCP_DAILY_CAP=50
  ```

  상태 파일은 `~/.config/tistory-mcp/ratelimit.json` 이고 일일 카운트는 로컬 날짜가 바뀌면
  리셋된다. 클라이언트 둘을 동시에 띄우면 프로세스 간에는 직렬화되지 않는다.

## 4. 본문·이미지·발행

### 4.1 "이미지 치환자 형식이 올바르지 않습니다"

- **원인**: 본문에 `[##_Image|…_##]` 처럼 생긴 구간이 있는데 `tistory_upload_image` 가 돌려준
  `substitution` 의 형태와 정확히 일치하지 않는다. 형태가 어긋난 치환자는 sanitize 를 우회하는
  통로가 되므로 본문 전체를 거부한다. 흔한 원인: 손으로 재조립, JSON 의 공백·키 순서 변경,
  `style` 값 오타, `CDM|1.3` 누락, 치환자 중간의 줄바꿈. 파일명에 `` < > " ' ` | { } [ ] \ `` 가
  들어간 치환자도 통과하지 않는다(한글·공백 파일명은 허용).
- **조치**: `substitution` 값을 **글자 그대로** 본문에 붙여 넣는다. 정렬을 바꾸고 싶으면
  업로드 시 `style` 인자로 지정한다(`alignCenter`/`alignLeft`/`alignRight`/`widthOrigin`).

### 4.2 이미지가 발행 직후엔 보이다가 나중에 깨짐

- **원인**: `attachments` 에 그 이미지의 `attachment_ref` 가 없거나, 본문 치환자 안의 `kage@…`
  값과 글자 단위로 다르다(예: `&amp;` 를 `&` 로 바꿈). 영구화되지 않은 첨부는 약 15일 뒤
  404 가 된다.
- **조치**: 같은 본문을 `tistory_update_post` 로 다시 보내되 `attachments` 에 모든 이미지의
  `attachment_ref` 를 그대로 넣는다. 이미 404 가 됐다면 이미지를 다시 업로드한다.

### 4.3 `tistory_update_post` 뒤 글에 마크다운 기호가 그대로 보임

- **원인**: 티스토리는 마크다운을 렌더하지 않는다. `tistory_update_post` 의 `content_format`
  기본값은 `'html'` 이라 마크다운을 넣으면 원문이 텍스트로 저장된다(`tistory_publish_post` 는
  기본이 `'markdown'`).
- **조치**: 마크다운을 보낼 때는 `content_format='markdown'` 을 지정한다.

### 4.4 발행 중 오류 — 재시도 전에 `tistory_list_posts`

- **증상**: 발행이 타임아웃이나 `… 글이 이미 생성됐을 수 있습니다. 재시도 전에
  tistory_list_posts 로 확인하세요` 로 끝났다.
- **원인**: `POST /manage/post.json` 은 항상 새 글을 만든다. 요청이 서버에 닿은 뒤 실패한
  경우 글은 이미 있을 수 있고, 그대로 재시도하면 둘이 된다.
- **조치**: `tistory_list_posts` 로 같은 제목의 글이 생겼는지 확인한 뒤에만 재시도한다.
  중복이 생겼으면 `tistory_delete_post(confirm=true)` 로 지운다.

### 4.5 태그 표기가 보낸 것과 다르게 보임

- **원인**: `"AI 코딩"` 을 보냈는데 공개 페이지에 `ai 코딩` 으로 보인 관찰이 1건 있다. 같은
  이름의 기존 태그 표기로 합쳐지는 것으로 보이며, 티스토리 쪽 동작이라 도구가 바꿀 수 없다.
  수정 응답의 `tags` 는 보낸 값(공백 정리 후)이다.
- **조치**: 표기가 중요하면 공개 페이지에서 확인한다. 기존 태그를 정리하는 것은 관리 화면에서.

### 4.6 "글 N 을(를) 찾지 못했습니다" / `meta_note` 가 붙음

- **원인**: 글 메타는 관리자 목록을 최근 20페이지까지만 훑어 찾는다. 그 밖의 오래된 글은
  `tistory_get_post` 가 메타 없이 본문만 돌려주고(`meta_note`), `tistory_update_post` 는 현재
  값(제목·카테고리·공개 범위)을 읽을 수 없어 거부한다. 글 번호 오타도 같은 증상이다.
- **조치**: 번호를 `tistory_list_posts`(`keyword` 로 제목 검색) 로 확인한다. 범위 밖 글의
  수정은 현재 지원하지 않는다.

### 4.7 "현재 태그를 읽지 못해 보존할 수 없습니다"

- **원인**: `tags` 를 생략한 수정은 글 페이지에서 현재 태그를 읽어 보존하는데, 페이지를 못
  읽었다(보호글·로그인 리다이렉트·네트워크). 태그를 모르는 채 full body 를 보내면 태그가
  지워지므로 거부한다.
- **조치**: `tags` 를 명시한다. 비우려면 `[]`.

### 4.8 그 밖의 거부 메시지

| 메시지 | 조치 |
|--------|------|
| `삭제는 되돌릴 수 없습니다. 사용자 확인 후 confirm=true 로 다시 호출하세요` | 의도된 동작. 사용자에게 확인한 뒤 `confirm=true` |
| `visibility='protected' 는 password 가 필요합니다` | `password` 지정 |
| `content 가 비어 있습니다. 빈 본문으로 덮어쓰기를 막기 위해 거부합니다` | 수정은 full body — 전체 본문을 보낸다 |
| `허용되지 않는 확장자` / `파일이 너무 큽니다` | png/jpg/jpeg/gif/webp, 20MB 이하 |
| 업로드 결과의 `width`/`height` 가 0 | JPEG 의 EXIF/ICC 가 커서 선두 64KB 에 크기가 없음 — `width`/`height` 인자로 지정 |

## 5. 디버깅

- **로그 레벨**: 클라이언트 설정 `env` 에 `TISTORY_MCP_LOG_LEVEL=DEBUG`. 로그는 stderr 로만
  나가며 클라이언트의 MCP 서버 로그에서 볼 수 있다.
- **핸드셰이크 확인**: `python scripts/mcp_probe.py uvx tistory-mcp` → `PROBE OK` 와 도구
  11개. 서버의 stderr 는 임시 디렉터리의 `tistory-mcp-probe-stderr.log` 에 남는다.
- **도구 1회 호출**: 클라이언트 없이 재현할 때.

  ```bash
  python scripts/mcp_call.py uvx tistory-mcp -- tistory_fetch_public_posts \
      '{"blog_url": "example.tistory.com", "limit": 3}'
  python scripts/mcp_call.py uvx tistory-mcp -- tistory_update_post @args.json 120
  ```

  큰 본문은 `@args.json` 으로 넘긴다(인자 하나는 128KiB 상한). 마지막 숫자는 대기 초.
  stderr 는 `tistory-mcp-call-stderr.log`. `args.json` 에는 미발행 초안이 들어가므로
  저장소에 커밋하지 않는다(`.gitignore` 에 있다).
- **세션 상태**: `uvx tistory-mcp status myblog.tistory.com` — `live` 가 `valid`/`expired`/
  `error: …` 중 무엇인지가 첫 번째 판별 기준이다.

## 6. 이슈 제출 시

- **절대 첨부하지 않는다**: 쿠키 값, 세션 JSON(`sessions/<host>.json`), HAR 파일, 브라우저
  프로필. 이것들만 있으면 누구든 블로그를 관리할 수 있다.
- 첨부할 것: `uvx tistory-mcp --version`, OS·Python 버전, 클라이언트 이름, 오류 메시지 전문,
  재현 절차. 로그를 붙이기 전에 쿠키 값이나 세션 파일 내용이 섞이지 않았는지 다시 본다.
- 비공식 API 라 티스토리 쪽 변경으로 깨졌을 가능성이 늘 있다. 어떤 도구가 어떤 HTTP 상태를
  받았는지(`→ HTTP 4xx`, `응답이 JSON 이 아닙니다` 등)가 가장 유용한 단서다.
