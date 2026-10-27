#!/usr/bin/env python3
"""Probe any stdio MCP server: initialize + tools/list (development / CI smoke test).

Usage: mcp_probe.py <server_cmd...>        e.g.  mcp_probe.py uvx tistory-mcp
Exit code 0 and a "PROBE OK" line mean the handshake worked. The server's stderr goes to
tistory-mcp-probe-stderr.log in the temp directory.
"""

import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

CMD = sys.argv[1:]
STDERR_LOG = Path(tempfile.gettempdir()) / "tistory-mcp-probe-stderr.log"
TIMEOUT = 120


def main() -> int:
    if not CMD:
        print(__doc__, file=sys.stderr)
        return 2
    errf = open(STDERR_LOG, "wb")
    proc = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errf)

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
                if remain <= 0:
                    return None
                if proc.poll() is not None:
                    return None
                lock.wait(min(remain, 1.0))
            return responses[msg_id]

    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "tistory-mcp-probe", "version": "0.1"},
            },
        }
    )
    init = wait_for(1, TIMEOUT)
    if init is None:
        print(f"FAIL: initialize 응답 없음 (exit={proc.poll()})")
        proc.kill()
        return 1
    info = init.get("result", {})
    print("=== initialize ===")
    print("serverInfo:", json.dumps(info.get("serverInfo"), ensure_ascii=False))
    print("protocolVersion:", info.get("protocolVersion"))
    print("capabilities:", json.dumps(info.get("capabilities"), ensure_ascii=False))

    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tl = wait_for(2, 60)
    if tl is None:
        print(f"FAIL: tools/list 응답 없음 (exit={proc.poll()})")
        proc.kill()
        return 1
    tools = tl.get("result", {}).get("tools", [])
    print(f"=== tools/list: {len(tools)} tools ===")
    for t in tools:
        desc = (t.get("description") or "").split("\n")[0][:80]
        print(f"- {t['name']}: {desc}")

    proc.kill()
    print("PROBE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
