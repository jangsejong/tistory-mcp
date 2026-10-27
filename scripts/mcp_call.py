#!/usr/bin/env python3
"""Call one tool on any stdio MCP server (development helper).

Usage: mcp_call.py <server_cmd...> -- <tool_name> <json_args | @args.json> [wait_sec]
Prints the result's content[].text to stdout; prefixes [TOOL ERROR] when isError is set.
Pass large bodies as `@file.json` (a single command-line argument is capped at 128KiB).
The server's stderr goes to tistory-mcp-call-stderr.log in the temp directory.

Example:
  python scripts/mcp_call.py uvx tistory-mcp -- tistory_fetch_public_posts \
      '{"blog_url": "example.tistory.com", "limit": 3}'
"""

import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

STDERR_LOG = Path(tempfile.gettempdir()) / "tistory-mcp-call-stderr.log"


def main() -> int:
    argv = sys.argv[1:]
    sep = argv.index("--")
    cmd = argv[:sep]
    tool = argv[sep + 1]
    raw_args = argv[sep + 2]
    if raw_args.startswith("@"):
        with open(raw_args[1:], encoding="utf-8") as f:
            raw_args = f.read()
    tool_args = json.loads(raw_args)
    wait = float(argv[sep + 3]) if len(argv) > sep + 3 else 60.0

    errf = open(STDERR_LOG, "wb")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errf)
    responses: dict[int, dict] = {}
    lock = threading.Condition()

    def reader() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print(f"[stdout 비JSON] {line[:200]}", file=sys.stderr)
                continue
            if "id" in msg:
                with lock:
                    responses[msg["id"]] = msg
                    lock.notify_all()

    threading.Thread(target=reader, daemon=True).start()

    def send(obj: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write((json.dumps(obj) + "\n").encode())
        proc.stdin.flush()

    def wait_for(msg_id: int, timeout: float) -> dict | None:
        deadline = time.monotonic() + timeout
        with lock:
            while msg_id not in responses:
                remain = deadline - time.monotonic()
                if remain <= 0 or proc.poll() is not None:
                    return None
                lock.wait(min(remain, 1.0))
            return responses[msg_id]

    def shutdown() -> None:
        try:
            assert proc.stdin is not None
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()

    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "tistory-mcp-call", "version": "0.1"},
            },
        }
    )
    if wait_for(1, 60) is None:
        print(f"FAIL: initialize 응답 없음 (exit={proc.poll()})")
        shutdown()
        return 1
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    send(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool, "arguments": tool_args},
        }
    )
    resp = wait_for(2, wait)
    if resp is None:
        print(f"FAIL: tools/call({tool}) 응답 없음 (wait={wait}s, exit={proc.poll()})")
        shutdown()
        return 1

    if "error" in resp:
        print(f"[RPC ERROR] {json.dumps(resp['error'], ensure_ascii=False)}")
        shutdown()
        return 1

    result = resp.get("result", {})
    if result.get("isError"):
        print("[TOOL ERROR]")
    for c in result.get("content", []):
        if c.get("type") == "text":
            print(c["text"])
        else:
            print(f"[{c.get('type')} content — 텍스트 아님]")
    shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
