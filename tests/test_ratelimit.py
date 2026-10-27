import json

import pytest

from tistory_mcp.ratelimit import RateLimiter, RateLimitError


def test_interval_and_daily_cap(tmp_path):
    now = [1_800_000_000.0]
    rl = RateLimiter(tmp_path / "rl.json", min_interval_sec=60, daily_cap=2, clock=lambda: now[0])
    rl.check_and_record("publish")
    with pytest.raises(RateLimitError, match="간격"):
        rl.check_and_record("publish")
    now[0] += 61
    rl.check_and_record("publish")
    now[0] += 61
    with pytest.raises(RateLimitError, match="일일 상한"):
        rl.check_and_record("publish")
    # 새 인스턴스도 파일 상태를 이어받는다
    rl2 = RateLimiter(tmp_path / "rl.json", min_interval_sec=60, daily_cap=2, clock=lambda: now[0])
    with pytest.raises(RateLimitError):
        rl2.check_and_record("update")
    # 하루가 지나면 카운트 리셋
    now[0] += 86_400
    rl2.check_and_record("update")


def test_zero_disables(tmp_path):
    rl = RateLimiter(tmp_path / "rl.json", min_interval_sec=0, daily_cap=0)
    for _ in range(5):
        rl.check_and_record("publish")


def test_save_is_atomic_and_leaves_no_tmp(tmp_path):
    path = tmp_path / "rl.json"
    rl = RateLimiter(path, min_interval_sec=0, daily_cap=5)
    rl.check_and_record("publish")
    assert path.is_file()
    # 임시 파일이 남지 않아야 한다(다음 로드가 반쪽 파일을 읽지 않도록)
    assert list(tmp_path.glob("*.tmp")) == []


def test_corrupt_state_file_does_not_crash(tmp_path):
    path = tmp_path / "rl.json"
    path.write_text('{"day": "2026-09-17", "cou', encoding="utf-8")  # 잘린 JSON
    RateLimiter(path, min_interval_sec=0, daily_cap=5).check_and_record("publish")
    assert json.loads(path.read_text(encoding="utf-8"))["count"] == 1


def test_concurrent_calls_let_only_one_through(tmp_path):
    import threading

    rl = RateLimiter(tmp_path / "rl.json", min_interval_sec=60, daily_cap=0)
    results: list[bool] = []
    start = threading.Barrier(8)

    def go() -> None:
        start.wait()
        try:
            rl.check_and_record("publish")
            results.append(True)
        except RateLimitError:
            results.append(False)

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1
