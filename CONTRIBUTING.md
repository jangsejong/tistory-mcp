# 기여 안내 (CONTRIBUTING)

tistory-mcp 에 관심을 가져 주셔서 감사합니다. 이 문서는 개발 환경 준비,
검사 명령, 코드 규칙, 릴리스 전 확인 절차를 정리한 것입니다.

> tistory-mcp 는 **비공식** 프로젝트이며 카카오·티스토리와 아무 관계가
> 없습니다. 목적은 "내 블로그를 위한 AI 글쓰기 보조 — 공개는 사람이 검토한
> 뒤" 입니다. 대량·스팸 발행, 검색엔진 조작, 본인 소유가 아닌 블로그 조작에
> 쓰이는 기능이나 변경은 받지 않습니다.

## 목차

1. [개발 환경 준비](#1-개발-환경-준비)
2. [검사](#2-검사-pr-전에-모두-통과)
3. [코드 규칙](#3-코드-규칙)
4. [버전과 Changelog](#4-버전과-changelog)
5. [릴리스 전 실계정 수동 검증](#5-릴리스-전-실계정-수동-검증)
6. [릴리스 절차](#6-릴리스-절차-관리자)
7. ["티스토리가 바뀌었어요" 신고](#7-티스토리가-바뀌었어요-신고)
8. [PR 체크리스트](#8-pr-체크리스트)

## 1. 개발 환경 준비

Python 3.11 이상이 필요합니다.

### 한 번에 (권장)

```bash
git clone https://github.com/jangsejong/tistory-mcp.git
cd tistory-mcp
bash scripts/setup.sh               # venv + 의존성 + 로그인용 Chromium + ruff/pytest 실행
bash scripts/setup.sh --no-browser  # Chromium(약 300MB) 다운로드 생략
```

### 수동

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[dev]"             # pytest + ruff 포함
tistory-mcp install-browser         # 로그인 창용 Chromium (Chrome/Edge 가 있으면 생략 가능)
```

## 2. 검사 (PR 전에 모두 통과)

```bash
ruff check src tests scripts
ruff format --check src tests scripts
pytest -q
```

MCP 핸드셰이크까지 확인하려면:

```bash
python scripts/mcp_probe.py .venv/bin/tistory-mcp   # "=== tools/list: 11 tools ===" 와 "PROBE OK"
```

CI(`.github/workflows/ci.yml`)도 같은 명령을 돌립니다 — ruff(ubuntu),
pytest(ubuntu/macOS/Windows × Python 3.11/3.12/3.13), 그리고 `uv build` 로
만든 wheel 을 새 venv 에 설치해 `tistory-mcp --version` 과 probe 가 통과하는지
확인합니다.

## 3. 코드 규칙

### 엔드포인트 변경은 `src/tistory_mcp/client.py` 에서만

티스토리 내부 API 의 URL·요청 본문·응답 해석·세션 만료 감지는 모두
`client.py` 에 있습니다. `server.py` 의 도구 함수나 다른 모듈에 엔드포인트
지식을 넣지 마세요. 티스토리가 바뀌었을 때 **한 파일만 고치면 되게**
유지하는 것이 이 프로젝트의 핵심 설계입니다.

### stdio 규칙 — 서버 코드에서 stdout 출력 금지

MCP stdio 서버는 stdout 이 곧 프로토콜 채널입니다. `print()` 한 줄이
클라이언트와의 연결을 깨뜨립니다. 진단 메시지는 `logging` 으로 남기고
(stderr 로 나갑니다), `print` 는 터미널 전용 CLI 서브커맨드
(`login` / `status` / `logout` 등)에서만 씁니다.

### 테스트는 네트워크 없이

- 모든 HTTP 는 `httpx.MockTransport` 로 가짜 응답을 줍니다. 실제 티스토리나
  실계정을 호출하는 테스트는 pytest 에 넣지 않습니다.
- `tests/conftest.py` 의 autouse 픽스처가 `TISTORY_MCP_HOME` 을 임시 디렉터리로
  바꿉니다. 테스트가 실제 `~/.config/tistory-mcp/` 를 건드리면 안 됩니다.
- 테스트·문서의 블로그 주소는 `myblog.tistory.com` 또는 `example.tistory.com`
  만 씁니다. 실제 블로그 주소, 글 번호, 쿠키 값은 넣지 않습니다.
- POSIX 파일 권한(0600) 검사처럼 OS 에 따라 달라지는 테스트는 Windows 에서
  `pytest.mark.skipif` 로 건너뜁니다(이미 예가 있습니다).

### 쿠키·세션 파일은 절대 커밋하지 않기

`sessions/`, `*.session.json`, `storage_state*.json`, `*.har`, `.env`,
`args.json` 은 `.gitignore` 에 있습니다. 그래도 커밋 전에 `git status` 로
한 번 더 확인하세요. 세션 파일은 블로그 관리 권한 그 자체입니다.

### 한글 줄 폭

ruff 설정은 `line-length = 100` 이지만, E501 은 동아시아 문자를 폭 2로 셉니다.
한글이 대부분인 줄(docstring·주석·오류 메시지)은 **45자 안팎**에서 끊어야
통과합니다.

### 그 밖에

- 기존 스타일을 따릅니다. 요청 범위 밖의 리팩터링·기능 추가는 별도 PR 로.
- 도구 설명(`title`·description)은 영문 + 한국어 병기를 유지합니다.
- 새 의존성은 꼭 필요한 경우에만, `pyproject.toml` 에 상한을 두고 추가합니다.

## 4. 버전과 Changelog

사용자가 체감하는 변경(도구 동작, 기본값, CLI, 설치 방법)이 있으면 PR 에
다음을 함께 넣습니다.

1. `src/tistory_mcp/__init__.py` 의 `__version__` 을 올립니다 (SemVer).
2. README 의 `## Changelog` 맨 위에 항목을 추가합니다.

   ```markdown
   ### vX.Y.Z (YYYY-MM-DD)
   - 변경 내용을 한 줄씩
   ```

3. 릴리스하는 PR 이라면 `server.json` 의 `version` 과 `packages[0].version`,
   `plugins/tistory/.claude-plugin/plugin.json` 의 `version` 도 같은 값으로
   맞춥니다. (`release.yml` 은 태그 `vX.Y.Z` 가 `__version__`·`server.json`
   과 다르면 빌드 단계에서 실패합니다.)

## 5. 릴리스 전 실계정 수동 검증

pytest 는 네트워크를 쓰지 않으므로, 릴리스 전에는 관리자가 **자기 블로그**
에서 아래 순서를 한 번 직접 돌립니다. 테스트 글은 비공개로 만들고 마지막에
지웁니다.

| # | 도구 | 확인할 것 |
|---|------|-----------|
| 1 | `tistory_session_init` | 브라우저 로그인 → 세션 파일 생성(0600) |
| 2 | `tistory_session_status` | `valid: true` |
| 3 | `tistory_get_categories` | 카테고리 id 목록 |
| 4 | `tistory_publish_post` (private) | 비공개 글 생성, 글 번호 반환 |
| 5 | `tistory_update_post` | 제목/본문 수정 반영 |
| 6 | `tistory_upload_image` + 이미지 포함 발행 | 치환자·첨부 참조가 그대로 붙음 |
| 7 | `tistory_get_post` | 렌더된 본문(HTML)에 이미지·서식 유지 |
| 8 | `tistory_save_draft` | 에디터 "이어서 작성" 에 초안 표시 |
| 9 | `tistory_delete_post` (`confirm=true`) | 테스트 글 삭제 |

결과는 PR 설명에 **도구명만** 적습니다(블로그 주소·글 번호·제목·쿠키 금지).

## 6. 릴리스 절차 (관리자)

1. 4절의 버전·Changelog 반영, 5절 검증 완료.
2. `main` 에서 태그를 만들어 푸시합니다: `git tag vX.Y.Z && git push origin vX.Y.Z`
3. `.github/workflows/release.yml` 이 순서대로 실행합니다.
   태그-버전 검사 → `uv build` → PyPI(trusted publishing) → MCP Registry
   (`mcp-publisher`, PyPI 반영 지연에 대비해 재시도) → GitHub Release(자동 노트).
4. PyPI 반영 뒤 `uvx tistory-mcp --version` 으로 확인합니다.

최초 1회 필요한 수동 설정(PyPI pending publisher, GitHub Environment `pypi`)은
`release.yml` 맨 위 주석에 있습니다.

## 7. "티스토리가 바뀌었어요" 신고

도구가 갑자기 HTTP 4xx/5xx 를 돌려주거나 응답 형식이 달라졌다면 티스토리
내부 API 가 바뀐 것일 수 있습니다. 이슈 템플릿 **「티스토리 변경으로 깨짐」**
으로 다음을 알려 주세요.

- 도구 이름, HTTP 상태 코드, 언제부터(날짜), 응답 요지(앞부분 몇 줄)
- `tistory-mcp --version` 출력, 클라이언트, OS
- **쿠키 값·세션 JSON·HAR·로그인 URL 은 절대 첨부하지 않습니다.**
  로그를 붙일 때는 `Cookie:` / `Set-Cookie:` 줄을 지우세요.

고칠 때는 `client.py` 만 바꾸고, `httpx.MockTransport` 로 새 응답 형식의
테스트를 추가합니다.

## 8. PR 체크리스트

`.github/PULL_REQUEST_TEMPLATE.md` 의 항목을 채워 주세요. 요약하면:

- [ ] ruff check / ruff format --check / pytest 통과
- [ ] 테스트·문서에 실제 호스트·쿠키 없음
- [ ] 체감 변경이면 README Changelog 항목 + `__version__` 증가
- [ ] 실계정 검증 여부(했음 / 안 했음 / 해당 없음)와 확인한 도구명

행동 강령은 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), 보안 신고는
[SECURITY.md](SECURITY.md) 를 봐 주세요.
