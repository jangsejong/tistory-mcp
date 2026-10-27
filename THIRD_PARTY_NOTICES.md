# Third-Party Notices

This file lists third-party work that `tistory-mcp` is derived from or depends on.
`tistory-mcp` itself is released under the MIT License (see `LICENSE`).

## kim-se-hee/tistory-mcp (MIT)

- Repository: https://github.com/kim-se-hee/tistory-mcp
- License: MIT (full text below)

The endpoint documentation in this project (`docs/ARCHITECTURE.md`, section 4 "엔드포인트
기준선") and the endpoint baseline implemented in `src/tistory_mcp/client.py` — the admin JSON
API paths, request body fields, session-expiry signals and the image substitution /
attachment reference format — are derived from the observations recorded in that project's
`docs/api.md`. **No code was copied from that project.** It is a separate TypeScript project
published on npm; this project is an independent Python implementation.

이 프로젝트의 엔드포인트 문서(`docs/ARCHITECTURE.md` 4절)와 `client.py` 의 엔드포인트
기준선은 위 프로젝트의 `docs/api.md` 에 기록된 관찰에서 파생되었습니다. 해당 프로젝트의
코드는 복사하지 않았습니다.

```
MIT License

Copyright (c) 2026 kim-se-hee

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Runtime dependencies

This project bundles no third-party source code. Its runtime dependencies — `mcp`, `httpx`,
`playwright`, `markdown-it-py`, `nh3`, `beautifulsoup4`, `pydantic` and the optional
`keyring` — are installed from PyPI under their own licenses, which are included in each
package's distribution. The Chromium build downloaded by `tistory-mcp install-browser` is
provided by Playwright and is not part of this package.

Tistory and Kakao are trademarks of their respective owners. This project is not affiliated
with, endorsed by or supported by Kakao Corp. or Tistory.
