<h1 align="center">tistory-mcp</h1>

<p align="center"><b>An unofficial MCP server for Tistory (티스토리) blogs — an AI writing assistant for Claude Code, Cursor and other MCP clients, where a human reviews before anything goes public.</b></p>
<p align="center"><a href="https://github.com/jangsejong/tistory-mcp/blob/main/README.md">한국어 README</a> (primary, includes the Changelog)</p>

[![PyPI](https://img.shields.io/pypi/v/tistory-mcp)](https://pypi.org/project/tistory-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/tistory-mcp)](https://pypi.org/project/tistory-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jangsejong/tistory-mcp/blob/main/LICENSE)
[![CI](https://github.com/jangsejong/tistory-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jangsejong/tistory-mcp/actions/workflows/ci.yml)

[<img src="https://img.shields.io/badge/VS_Code-VS_Code?style=flat-square&label=Install%20Server&color=0098FF" alt="Install in VS Code">](https://insiders.vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F%257B%2522name%2522%253A%2522tistory%2522%252C%2522command%2522%253A%2522uvx%2522%252C%2522args%2522%253A%255B%2522tistory-mcp%2522%255D%257D) [<img src="https://cursor.com/deeplink/mcp-install-dark.svg" alt="Install in Cursor">](https://cursor.com/en/install-mcp?name=tistory&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJ0aXN0b3J5LW1jcCJdfQ%3D%3D)

> **Unofficial. Not affiliated with Kakao or Tistory.** Tistory's Open API was shut down in February 2024. This server works with a one-time headed Kakao login (you complete the Kakao login and the KakaoTalk push approval in a browser window); the cookies are saved locally and the admin JSON API that Tistory's own dashboard uses is called with httpx. Endpoint knowledge follows the MIT-licensed observations in [kim-se-hee/tistory-mcp](https://github.com/kim-se-hee/tistory-mcp), a **separate TypeScript project** published on npm as `tistory-mcp`. **`npx tistory-mcp` and `uvx tistory-mcp` are different projects** — this repository is the Python/PyPI one.

## What it does

- Converts markdown to HTML with Tistory editor styling attributes, so posts look like they were written in the editor.
- Publishes new posts (**private by default**), updates, deletes, lists categories, and reads posts including private ones.
- Uploads images and returns both the body substitution and the attachment reference the post needs to keep the image alive.
- Saves a draft into the editor's autosave slot (restored as "continue writing" next time).
- Reads any Tistory blog's public posts via RSS — no login needed.
- Terminal CLI (`login` / `status` / `logout`) so you can log in without hitting MCP client tool timeouts.

Default flow: write → publish as a **private** draft → read it in Tistory → switch it to public.

## Safety defaults

| | Default | Override |
|---|---|---|
| Publish visibility | **private** | pass `visibility="public"` explicitly |
| Delete | refused without `confirm=true`; MCP `destructiveHint` set | — |
| Publish/update rate | 60 s apart, 20 per day (thread-locked within the process) | `TISTORY_MCP_MIN_INTERVAL_SEC`, `TISTORY_MCP_DAILY_CAP` (0 disables) |
| Publish retry | never automatic — every `publish` call creates a **new** post | — |
| Target hosts | `*.tistory.com` only | `TISTORY_MCP_ALLOW_ANY_HOST=1` |
| Browser CDP address | loopback only | `TISTORY_MCP_ALLOW_REMOTE_CDP=1` |
| Body HTML | sanitized with [nh3](https://github.com/messense/nh3): `script`/`on*` removed, `http`/`https`/`mailto`/`tel` only | — |
| Image substitutions | must match exactly what `tistory_upload_image` returned | — |

## Quick start

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then (optional if Chrome or Edge is installed — the login tries bundled Chromium → Chrome → Edge):

   ```bash
   uvx tistory-mcp install-browser      # Playwright Chromium, once, ~300MB
   ```

2. Register the server. Claude Code:

   ```bash
   claude mcp add tistory --scope user -- uvx tistory-mcp
   ```

   Any client that takes the common `mcpServers` form (Claude Desktop `claude_desktop_config.json`, Cursor `~/.cursor/mcp.json`, Gemini CLI `~/.gemini/settings.json`, …):

   ```json
   {"mcpServers":{"tistory":{"command":"uvx","args":["tistory-mcp"]}}}
   ```

   VS Code (`.vscode/mcp.json`) uses a `servers` key with `"type": "stdio"`; Codex CLI uses `[mcp_servers.tistory]` in `~/.codex/config.toml` (or `codex mcp add tistory -- uvx tistory-mcp`). The install buttons above do the same for VS Code and Cursor.

3. In a new session, tell the AI:

   > connect my Tistory blog myblog.tistory.com

   A browser window opens. Finish the Kakao login and approve the KakaoTalk push. Cookies are saved under `~/.config/tistory-mcp/sessions/` (mode 0600). The session can be short — in testing it expired after about an hour; log in again when a tool says so.

If no browser window can appear (WSL, SSH, containers) or the client times out during login, log in from a terminal instead:

```bash
tistory-mcp login myblog.tistory.com                                   # headed login, waits up to 5 minutes
tistory-mcp login myblog.tistory.com --cdp-url http://127.0.0.1:9222   # attach to a browser started with --remote-debugging-port=9222
```

Use a dedicated `--user-data-dir` for that browser, since its cookies are read. For a remote server, forward the port with `ssh -L 9222:localhost:9222`.

## Tools

| Tool | Kind | What it does | Login |
|---|---|---|---|
| `tistory_session_init` | write | Opens a browser for the Kakao login and saves the cookies. `cdp_url` attaches to an already-running browser | performs it |
| `tistory_session_status` | read | Saved session exists? When does it expire? Is it live right now? | no |
| `tistory_get_categories` | read | Category tree with integer ids (`category` in publish/update takes the id) | yes |
| `tistory_list_posts` | read | Admin list incl. private posts; keyword / visibility / category / page | yes |
| `tistory_get_post` | read | Metadata + rendered body HTML, private posts included | yes |
| `tistory_fetch_public_posts` | read | RSS of any blog | **no** |
| `tistory_publish_post` | write | Creates a **new** post; markdown → editor-styled HTML; **private** by default; rate-limited; never auto-retry | yes |
| `tistory_update_post` | write | Full-body update; keeps title/category/visibility/slug/tags when omitted; `content_format` defaults to `html` | yes |
| `tistory_delete_post` | destructive | Permanent; requires `confirm=true` | yes |
| `tistory_upload_image` | write | Returns `substitution` (paste into the body) + `attachment_ref` (pass in `attachments`, or the image breaks after ~15 days) | yes |
| `tistory_save_draft` | write | Writes the editor's single autosave slot — not a list of drafts | yes |

Tool titles and descriptions are bilingual (English + Korean).

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `TISTORY_MCP_HOME` | `~/.config/tistory-mcp` | Session and rate-limit state. Honors `XDG_CONFIG_HOME`; on Windows it is `C:\Users\<you>\.config\tistory-mcp` |
| `TISTORY_MCP_SESSION_STORE` | `file` | `file` (0600 JSON) or `keyring` (needs `pip install "tistory-mcp[keyring]"`; Linux needs Secret Service; not supported on Windows) |
| `TISTORY_MCP_MIN_INTERVAL_SEC` | `60` | Minimum seconds between publish/update; `0` disables |
| `TISTORY_MCP_DAILY_CAP` | `20` | Publish/update calls per day; `0` disables |
| `TISTORY_MCP_ALLOW_ANY_HOST` | unset | `1` allows hosts other than `*.tistory.com` (custom domains) |
| `TISTORY_MCP_CDP_URL` | unset | CDP address used when the `cdp_url` argument is omitted |
| `TISTORY_MCP_ALLOW_REMOTE_CDP` | unset | `1` allows non-loopback CDP addresses |
| `TISTORY_MCP_LOG_LEVEL` | `INFO` | stderr log level |

CLI: `tistory-mcp` (no arguments) runs the stdio server; `tistory-mcp --version`, `install-browser`, `login <blog> [--cdp-url URL] [--timeout SEC]`, `status <blog>`, `logout <blog>`.

## Limitations and disclaimer

- Unofficial. It can stop working whenever Tistory changes its internal API.
- Using it may conflict with the Tistory/Kakao terms of service. Any account risk is yours.
- Fully unattended operation is impossible by design (KakaoTalk push approval). Sessions can expire after as little as an hour or so; log in again when a tool says so.
- No telemetry. Cookies never leave your machine except in requests to Tistory.
- All 11 tools were verified on a real blog (2026-10-27, with private test posts that were deleted afterwards) — see the verification table in the Korean README.

**Not for:** mass or bulk posting, spam, SEO abuse, or posting to blogs you do not own. This is a writing assistant for your own blog, with a human reading the post before it goes public.

## Security

The saved cookies are your blog's admin credentials. Never attach cookies, session JSON or HAR files to issues. Report vulnerabilities as described in [SECURITY.md](https://github.com/jangsejong/tistory-mcp/blob/main/SECURITY.md).

## Contributing, license, credits

- Contributions: [CONTRIBUTING.md](https://github.com/jangsejong/tistory-mcp/blob/main/CONTRIBUTING.md) · internals: [docs/ARCHITECTURE.md](https://github.com/jangsejong/tistory-mcp/blob/main/docs/ARCHITECTURE.md) · troubleshooting: [docs/TROUBLESHOOTING.md](https://github.com/jangsejong/tistory-mcp/blob/main/docs/TROUBLESHOOTING.md)
- License: [MIT](https://github.com/jangsejong/tistory-mcp/blob/main/LICENSE)
- Credits: [kim-se-hee/tistory-mcp](https://github.com/kim-se-hee/tistory-mcp) (MIT) for the endpoint observations in its `docs/api.md` — a separate project; [aiarchitecturedev/aiarchitect-blog-mcp](https://github.com/aiarchitecturedev/aiarchitect-blog-mcp) for the tool-annotation and fail-closed patterns.
- Changelog: see the [Korean README](https://github.com/jangsejong/tistory-mcp/blob/main/README.md#changelog).
