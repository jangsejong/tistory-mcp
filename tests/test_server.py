import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tistory_mcp import server as srv
from tistory_mcp.session import SessionStore, StoredSession

EXPECTED_TOOLS = {
    "tistory_session_init",
    "tistory_session_status",
    "tistory_get_categories",
    "tistory_list_posts",
    "tistory_get_post",
    "tistory_fetch_public_posts",
    "tistory_publish_post",
    "tistory_update_post",
    "tistory_delete_post",
    "tistory_upload_image",
    "tistory_save_draft",
}


@pytest.mark.anyio
async def test_tools_registered_with_annotations():
    tools = await srv.server.list_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
    by = {t.name: t.model_dump(by_alias=True) for t in tools}
    assert by["tistory_delete_post"]["annotations"]["destructiveHint"] is True
    assert by["tistory_list_posts"]["annotations"]["readOnlyHint"] is True
    assert by["tistory_publish_post"]["annotations"]["readOnlyHint"] is False
    schema = by["tistory_publish_post"]["inputSchema"]
    assert schema["required"] == ["blog_url", "title", "content"]
    assert schema["properties"]["visibility"]["default"] == "private"


def test_client_requires_session():
    with pytest.raises(ToolError, match="session_init"):
        srv._client("nosession.tistory.com")


def test_client_with_stored_session():
    SessionStore().save(
        StoredSession(
            host="example.tistory.com",
            cookies=[{"name": "TSSESSION", "value": "v", "domain": ".tistory.com", "expires": -1}],
            saved_at=1,
        )
    )
    c = srv._client("https://example.tistory.com/")
    assert c.host == "example.tistory.com"
    c.close()


def test_delete_requires_confirm():
    with pytest.raises(ToolError, match="confirm"):
        srv.tistory_delete_post("example.tistory.com", "1")


def test_update_rejects_empty_content():
    with pytest.raises(ToolError, match="비어"):
        srv.tistory_update_post("example.tistory.com", "1", "   ")


def test_prepare_body_rules():
    with pytest.raises(ToolError, match="password"):
        srv._prepare_body(
            title="t",
            content="x",
            content_format="markdown",
            category=0,
            tags=None,
            visibility="protected",
            password=None,
            slogan="",
            attachments=None,
            post_type="post",
        )
    body = srv._prepare_body(
        title="t",
        content="# h",
        content_format="markdown",
        category=3,
        tags=[" a ", "", "b"],
        visibility="public",
        password=None,
        slogan="",
        attachments=["kage@x"],
        post_type="post",
    )
    assert body["content"] == "<h1>h</h1>\n" and body["tag"] == "a,b" and body["visibility"] == 20
    assert json.dumps(body)  # 직렬화 가능
    styled = srv._prepare_body(
        title="t",
        content="문단",
        content_format="markdown",
        category=0,
        tags=None,
        visibility="private",
        password=None,
        slogan="",
        attachments=None,
        post_type="post",
    )
    assert styled["content"] == '<p data-ke-size="size16">문단</p>\n'  # 발행·수정 경로도 서식 적용


def test_publish_failures_do_not_consume_rate_limit():
    from tistory_mcp.config import settings

    with pytest.raises(ToolError, match="tistory.com"):
        srv.tistory_publish_post("evil.example.com", "t", "x")
    with pytest.raises(ToolError, match="session_init"):
        srv.tistory_publish_post("nosession.tistory.com", "t", "x")
    assert not settings().ratelimit_path.exists()


def test_translate_passes_tool_error_through_unwrapped():
    # _client() 가 낸 ToolError 가 "ToolError: ..." 로 이중 래핑되면 안 된다
    original = ToolError("세션이 없습니다")
    assert srv._translate(original) is original
    with pytest.raises(ToolError) as ei:
        srv.tistory_get_categories("nosession.tistory.com")
    assert not str(ei.value).startswith("ToolError:")


def test_upload_image_keeps_user_supplied_dimension(tmp_path, monkeypatch):
    import struct

    png = tmp_path / "i.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 500, 600))

    class FakeClient:
        host = "example.tistory.com"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def upload_image(self, file_path):
            return {"url": "https://cdn/x?sig=1", "key": "K", "filename": "i.png", "size": 1}

    monkeypatch.setattr(srv, "_client", lambda blog_url: FakeClient())
    # width 만 지정 → height 만 헤더에서 채우고 width 는 사용자 값 유지
    out = srv.tistory_upload_image("example.tistory.com", str(png), width=300)
    assert (out["width"], out["height"]) == (300, 600)
    # 둘 다 미지정 → 둘 다 헤더값
    out = srv.tistory_upload_image("example.tistory.com", str(png))
    assert (out["width"], out["height"]) == (500, 600)


def test_get_post_degrades_when_admin_scan_misses(monkeypatch):
    class FakeClient:
        host = "example.tistory.com"
        cookie_header = "TSSESSION=v"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def find_post(self, pid):
            return None  # 최근 20페이지 밖의 오래된 글

    monkeypatch.setattr(srv, "_client", lambda blog_url: FakeClient())
    monkeypatch.setattr(
        srv,
        "fetch_public_post",
        lambda *a, **k: {"title": "T", "content_html": "<p>x</p>", "tags": []},
    )
    out = srv.tistory_get_post("example.tistory.com", "3")
    assert out["meta"] is None and "meta_note" in out
    assert out["content_html"] == "<p>x</p>"  # 본문은 그대로 돌려준다


def test_tools_have_titles_and_bilingual_descriptions(anyio_backend):
    import anyio

    async def go():
        return await srv.server.list_tools()

    tools = anyio.run(go, backend=anyio_backend)
    for t in tools:
        assert t.title and "(" in t.title, t.name  # "English (한국어)" titles
        assert t.description and t.description.strip(), t.name


def test_prepare_body_rejects_malformed_image_substitution():
    with pytest.raises(ToolError, match="치환자"):
        srv._prepare_body(
            title="t",
            content="[##_Image|<script>x</script>_##]",
            content_format="markdown",
            category=0,
            tags=None,
            visibility="private",
            password=None,
            slogan="",
            attachments=None,
            post_type="post",
        )


def test_save_draft_rejects_malformed_image_substitution(monkeypatch):
    monkeypatch.setattr(srv, "_client", lambda blog_url: (_ for _ in ()).throw(AssertionError))
    with pytest.raises(ToolError, match="치환자"):
        srv.tistory_save_draft("example.tistory.com", "t", "[##_Image|<b>x</b>_##]")


def test_cli_version_and_help_do_not_start_server(capsys):
    from tistory_mcp import __version__

    with pytest.raises(SystemExit) as ei:
        srv.main(["--version"])
    assert ei.value.code == 0 and __version__ in capsys.readouterr().out
    with pytest.raises(SystemExit) as ei:
        srv.main(["--help"])
    assert ei.value.code == 0 and "install-browser" in capsys.readouterr().out


def test_cli_status_and_logout_without_session(capsys):
    with pytest.raises(SystemExit) as ei:
        srv.main(["status", "nosession.tistory.com"])
    assert ei.value.code == 0
    assert json.loads(capsys.readouterr().out)["exists"] is False
    with pytest.raises(SystemExit) as ei:
        srv.main(["logout", "nosession.tistory.com"])
    assert ei.value.code == 1
    with pytest.raises(SystemExit) as ei:
        srv.main(["logout", "not-a-tistory.example.com"])
    assert ei.value.code == 1 and "tistory.com" in capsys.readouterr().err
