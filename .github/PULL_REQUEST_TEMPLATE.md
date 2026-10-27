## 요약

<!-- 무엇을, 왜 바꿨는지 2~3줄. 관련 이슈가 있으면 `Closes #번호` -->

## 변경 종류

- [ ] 버그 수정
- [ ] 기능 추가 / 동작 변경
- [ ] 티스토리 내부 API 변경 대응 (`src/tistory_mcp/client.py`)
- [ ] 문서 · CI · 패키징

## 체크리스트

- [ ] `ruff check src tests scripts` 와 `ruff format --check src tests scripts` 통과
- [ ] `pytest -q` 통과 (네트워크 없이 — `httpx.MockTransport`)
- [ ] 테스트·문서에 실제 블로그 주소·글 번호·쿠키 값이 없음 (예시는 `myblog.tistory.com` 만)
- [ ] 사용자가 체감하는 변경이면 README `## Changelog` 에 `### vX.Y.Z (YYYY-MM-DD)` 항목을 추가하고 `__version__` 을 올림
- [ ] 서버 코드(stdio)에 `print()` 를 추가하지 않음 (로그는 stderr)
- [ ] 엔드포인트 변경은 `client.py` 안에서만

## 실계정 검증

<!-- 하나에 표시하세요. 도구명만 적고 블로그 주소·글 번호·제목은 적지 않습니다. -->

- [ ] 했음 — 확인한 도구:
- [ ] 안 했음 — 이유:
- [ ] 해당 없음 (문서 · CI 만 변경)
