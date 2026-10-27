# 보안 정책 (Security Policy)

## 지원 버전

| 버전 | 보안 수정 |
|------|-----------|
| 0.x 최신 릴리스 | 지원 |
| 이전 0.x 릴리스 | 지원하지 않음 — 최신 버전으로 올려 주세요 |

0.x 는 아직 초기 단계라 보안 수정은 **최신 릴리스에만** 반영합니다.

## 취약점 신고 방법

**공개 이슈·Discussions·PR 에 취약점 내용을 올리지 마세요.**

GitHub 비공개 취약점 신고(Private Vulnerability Reporting)를 이용해 주세요.

- 신고 폼: https://github.com/jangsejong/tistory-mcp/security/advisories/new
- 또는 저장소 **Security** 탭 → **Report a vulnerability**

신고에 넣어 주시면 좋은 것: 영향받는 버전(`tistory-mcp --version` 출력),
재현 절차, 영향(어떤 권한·데이터가 노출되는지), 가능하면 수정 제안.

확인 회신은 보통 7일 안에 드리려 합니다. 수정판이 나올 때까지 내용은
비공개로 다루고, 수정 후 GitHub advisory 로 공개하며 신고자 크레딧을
표기합니다(원치 않으면 말씀해 주세요). 개인이 유지보수하는 비공식
오픈소스라 버그바운티는 없습니다.

### 절대 첨부하지 말아야 할 것

- 쿠키 값 (`Cookie:` / `Set-Cookie:` 헤더, 어떤 쿠키 이름이든)
- 세션 JSON (`~/.config/tistory-mcp/sessions/<host>.json` 의 내용)
- HAR 파일, 브라우저 네트워크 탭 내보내기
- 쿠키·토큰이 보이는 스크린샷, 일회성 토큰이 든 로그인 URL
- 본인 소유가 아닌 블로그로 재현한 결과

쿠키가 이미 노출됐다고 생각되면: 티스토리/카카오에서 모든 기기 로그아웃
→ `tistory-mcp logout <블로그>` 로 로컬 세션 삭제 → 필요하면 카카오 계정
비밀번호 변경.

## 범위 (In scope)

이 프로젝트 코드에서 다음과 관련된 문제는 보안 취약점으로 다룹니다.

- **쿠키 취급**: 세션 파일 권한(0600)·위치, keyring 저장, 로그·도구 응답·
  오류 메시지에 쿠키가 섞여 나오는 경우
- **본문 HTML 정화 우회**: nh3 정화를 피해 `script`·이벤트 핸들러·위험한
  링크 스킴이 발행 본문에 남는 경우(저장형 XSS)
- **호스트 allowlist 우회 / SSRF**: `*.tistory.com` 이 아닌 곳으로 쿠키가
  전송되게 만들 수 있는 입력(`blog_url` 정규화 우회 등)
- **CDP 로그인 모드**: `cdp_url` 로 붙은 브라우저에서 블로그 외 쿠키가
  보관·전송되는 경우, loopback 제한 우회
- **레이트리밋 우회**: 발행·수정 간격 / 일일 상한을 코드 결함으로 건너뛰는
  경우
- **이미지 치환자 검증 우회**: 업로드 결과와 다른 치환자가 통과하는 경우
- 의존성 취약점 중 이 서버의 실제 코드 경로로 악용 가능한 것

### 범위 밖

- 티스토리·카카오 서비스 자체의 취약점 → 해당 회사에 신고해 주세요.
- 사용자가 스스로 `TISTORY_MCP_ALLOW_ANY_HOST=1` 또는
  `TISTORY_MCP_ALLOW_REMOTE_CDP=1` 을 켠 구성에서만 생기는 문제
- 같은 OS 계정 권한을 이미 가진 공격자가 세션 파일을 읽는 것 — 로컬 계정
  보안은 OS 의 몫입니다.
- 실제 악용 경로가 없는 단순 의존성 버전 경고 → 일반 이슈 또는 Dependabot

## 이 서버가 다루는 데이터

- **저장하는 것**: 블로그 호스트별 티스토리 세션 쿠키. 파일 모드(기본)에서는
  `~/.config/tistory-mcp/sessions/<host>.json` 에 `0600` 권한으로, keyring
  모드(`TISTORY_MCP_SESSION_STORE=keyring`)에서는 OS 키체인에 저장됩니다.
- **쿠키가 뜻하는 것**: 그 **블로그의 관리 권한**(글 작성·수정·삭제)입니다.
  카카오 계정 권한이 아니며, 카카오 로그인 쿠키는 저장하지 않습니다.
- **CDP 로그인 모드**(`cdp_url`): 이미 떠 있는 브라우저에 붙어 그 브라우저의
  **모든 쿠키를 메모리로 읽은 뒤** 블로그 것만 남깁니다. 평소 쓰는
  프로필이 아니라 **전용 `--user-data-dir` 프로필**로 브라우저를 띄우는 것을
  권장합니다. CDP 주소는 기본적으로 loopback 만 허용합니다.
- **보내는 곳**: 네트워크 상대는 사용자의 티스토리 블로그(및 로그인 시
  카카오 로그인 페이지)뿐입니다. 텔레메트리·사용 통계·외부 서버 전송은
  없습니다.
- **발행 본문**: 마크다운 → HTML 변환 뒤 nh3 로 정화합니다. 이미지 치환자는
  `tistory_upload_image` 결과와 정확히 일치해야 통과합니다.
- **기본 안전장치**: 비공개 발행 기본, 삭제는 `confirm=true` 필요, 발행·수정
  60초 간격 · 하루 20회(환경변수로 조정, 0 = 해제).

## 허용되지 않는 사용

대량·자동 발행(스팸), 검색엔진 조작, 본인 소유가 아닌 블로그 조작에 이
소프트웨어를 쓰지 마세요. 그런 용도의 기능 요청·PR 은 받지 않습니다.
이 프로젝트는 비공식이며 카카오·티스토리와 무관하고, 티스토리 내부 API 가
바뀌면 언제든 동작을 멈출 수 있습니다.

---

## Security Policy (English summary)

- **Supported versions**: the latest 0.x release only.
- **Report privately** through GitHub Private Vulnerability Reporting:
  https://github.com/jangsejong/tistory-mcp/security/advisories/new
  (repository **Security** tab → **Report a vulnerability**). Please do not
  open a public issue.
- **Never attach** cookie values, session JSON files, HAR files, or
  screenshots that show cookies or login URLs.
- **In scope**: cookie handling, HTML sanitization (nh3) bypass / stored XSS,
  host allowlist bypass / SSRF, CDP login mode, rate-limit bypass, image
  substitution validation bypass.
- **Data model**: one headed Kakao login stores the blog's session cookies in
  a 0600 file (or the OS keyring). Those cookies grant management rights on
  that blog, not on the Kakao account; Kakao cookies are not stored. CDP mode
  reads all cookies of the attached browser into memory and keeps only the
  blog's, so run that browser with a dedicated `--user-data-dir` profile. No
  telemetry; the only network peer is the user's own Tistory blog.
- **Disallowed use**: bulk/spam posting, SEO abuse, blogs you do not own.
  Unofficial project, not affiliated with Kakao or Tistory; the internal API
  may change at any time.
