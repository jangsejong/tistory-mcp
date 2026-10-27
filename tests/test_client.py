import json

import httpx
import pytest

from tistory_mcp.client import (
    SessionExpiredError,
    TistoryApiError,
    TistoryClient,
    build_attachment_ref,
    build_image_substitution,
    validate_entry_url,
    validate_post_id,
)

HOST = "example.tistory.com"


def _client(handler):
    return TistoryClient(HOST, "TSSESSION=abc", transport=httpx.MockTransport(handler))


def test_common_headers_and_json_get():
    seen = {}

    def handler(req: httpx.Request):
        seen["headers"] = req.headers
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"rootLabel": "분류 전체보기", "categories": []})

    with _client(handler) as c:
        data = c.get_categories()
    assert data["rootLabel"] == "분류 전체보기"
    assert seen["url"] == f"https://{HOST}/manage/category.json"
    h = seen["headers"]
    assert h["cookie"] == "TSSESSION=abc"
    assert h["origin"] == f"https://{HOST}" and h["referer"].endswith("/manage/")
    assert h["accept"] == "application/json"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            302, headers={"location": "https://www.tistory.com/auth/login?redirectUrl=x"}
        ),
        httpx.Response(302, headers={"location": "https://accounts.kakao.com/login"}),
        httpx.Response(401),
        httpx.Response(200, text='<html><form id="loginKey">accounts.kakao.com</form></html>'),
    ],
)
def test_session_expiry_signals(response):
    with _client(lambda req: response) as c, pytest.raises(SessionExpiredError):
        c.get_categories()


def test_http_error_and_non_json():
    with (
        _client(lambda req: httpx.Response(500, text="boom")) as c,
        pytest.raises(TistoryApiError) as ei,
    ):
        c.get_categories()
    assert ei.value.status == 500 and "boom" in ei.value.body
    with (
        _client(lambda req: httpx.Response(200, text="<html>spa</html>")) as c,
        pytest.raises(TistoryApiError),
    ):
        c.get_categories()


def test_publish_post_body_defaults_and_entry_url():
    captured = {}

    def handler(req: httpx.Request):
        captured["method"] = req.method
        captured["path"] = req.url.path
        captured["body"] = json.loads(req.content)
        assert req.headers["content-type"].startswith("application/json")
        return httpx.Response(200, json={"entryUrl": f"https://{HOST}/42"})

    with _client(handler) as c:
        out = c.publish_post({"title": "t", "content": "<p>x</p>", "visibility": 20, "id": "999"})
    assert out == {"entry_url": f"https://{HOST}/42", "post_id": "42"}
    assert captured["method"] == "POST" and captured["path"] == "/manage/post.json"
    b = captured["body"]
    assert b["id"] == "0" and b["published"] == 1 and b["type"] == "post" and b["attachments"] == []
    assert b["visibility"] == 20 and b["recaptchaValue"] == "" and b["draftSequence"] is None


def test_publish_rejects_foreign_entry_url():
    with _client(
        lambda req: httpx.Response(200, json={"entryUrl": "https://other-example.tistory.com/1"})
    ) as c:
        with pytest.raises(TistoryApiError, match="host"):
            c.publish_post({"title": "t", "content": "x"})


def test_update_and_delete_paths():
    calls = []

    def handler(req: httpx.Request):
        calls.append((req.method, req.url.path))
        if req.method == "PUT":
            assert json.loads(req.content)["id"] == "18"
            return httpx.Response(200, json={"entryUrl": f"https://{HOST}/18"})
        return httpx.Response(200, json={"data": {"id": 18}})

    with _client(handler) as c:
        assert c.update_post("18", {"title": "t", "content": "x"})["post_id"] == "18"
        assert c.delete_post(18) == {"data": {"id": 18}}
    assert calls == [("PUT", "/manage/post/18.json"), ("DELETE", "/manage/post/18.json")]


def test_post_id_validation():
    assert validate_post_id(" 18 ") == "18"
    for bad in ["../x", "18.json", "-1", "abc", ""]:
        with pytest.raises(TistoryApiError):
            validate_post_id(bad)


def test_validate_entry_url_page_slug():
    assert validate_entry_url(HOST, f"https://{HOST}/pages/about") == "about"
    with pytest.raises(TistoryApiError):
        validate_entry_url(HOST, f"https://{HOST}/manage")
    with pytest.raises(TistoryApiError):
        validate_entry_url(HOST, None)


def test_list_posts_params_and_find_post():
    pages = {
        "1": [{"id": "10", "title": "a"}, {"id": "9", "title": "b"}],
        "2": [{"id": "8", "title": "c"}],
        "3": [],
    }
    seen = []

    def handler(req: httpx.Request):
        q = dict(req.url.params)
        seen.append(q)
        return httpx.Response(200, json={"items": pages[q["page"]], "total": 3})

    with _client(handler) as c:
        data = c.list_posts(keyword="k", search_type="content", visibility="private", category=7)
        assert data["total"] == 3
        assert seen[0] == {
            "category": "7",
            "page": "1",
            "searchKeyword": "k",
            "searchType": "content",
            "visibility": "hidden",  # server vocabulary differs from the tool's
        }
        assert c.find_post(8)["title"] == "c"
        assert c.find_post(99) is None


def test_upload_image_multipart_and_ref(tmp_path):
    png = tmp_path / "img.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    captured = {}

    def handler(req: httpx.Request):
        captured["ct"] = req.headers["content-type"]
        captured["body"] = req.content
        return httpx.Response(
            200,
            json={
                "name": "img.png",
                "url": "https://cdn.example/dna/KEY/abc/DEF/img.png?credential=c&expires=9&signature=s",
                "key": "KEY/abc/DEF",
                "filename": "img.png",
                "size": 24,
            },
        )

    with _client(handler) as c:
        up = c.upload_image(str(png))
    assert captured["ct"].startswith("multipart/form-data")
    assert b'name="file"; filename="img.png"' in captured["body"]
    ref = build_attachment_ref(up)
    assert ref == "kage@KEY/abc/DEF/img.png?credential=c&amp;expires=9&amp;signature=s"
    sub = build_image_substitution(ref, 300, 366)
    assert (
        sub == f"[##_Image|{ref}|CDM|1.3|"
        '{"originWidth":300,"originHeight":366,"style":"alignCenter"}_##]'
    )


def test_upload_image_rejects_bad_files(tmp_path):
    with _client(lambda req: httpx.Response(200, json={})) as c:
        with pytest.raises(TistoryApiError, match="확장자"):
            (tmp_path / "x.txt").write_text("x")
            c.upload_image(str(tmp_path / "x.txt"))
        with pytest.raises(TistoryApiError, match="없습니다"):
            c.upload_image(str(tmp_path / "missing.png"))


def test_autosave_body():
    captured = {}

    def handler(req: httpx.Request):
        captured["path"] = req.url.path
        captured["body"] = json.loads(req.content)
        return httpx.Response(200, text="")

    with _client(handler) as c:
        c.save_autosave(title="t", content="<p>x</p>", tags="a,b", category_id=3)
    assert captured["path"] == "/manage/autosave"
    assert captured["body"] == {
        "title": "t",
        "content": "<p>x</p>",
        "tags": "a,b",
        "categoryId": 3,
        "draftSequence": None,
        "totalWritingTimeMs": 0,
    }


def test_publish_failure_warns_about_possible_duplicate():
    # The POST may have gone through even when the response is unusable; the caller must be
    # told to check before retrying, because a retry would create a second post.
    with _client(lambda req: httpx.Response(500, text="boom")) as c:
        with pytest.raises(TistoryApiError, match="tistory_list_posts"):
            c.publish_post({"title": "t", "content": "x"})
    with _client(
        lambda req: httpx.Response(200, json={"entryUrl": "https://x.tistory.com/1"})
    ) as c:
        with pytest.raises(TistoryApiError, match="tistory_list_posts"):
            c.publish_post({"title": "t", "content": "x"})


def test_build_image_substitution_rejects_unknown_style():
    with pytest.raises(ValueError):
        build_image_substitution("kage@K/a.png", 1, 1, "floatLeft")


@pytest.mark.parametrize(
    ("tool_value", "server_value"),
    [("all", "all"), ("public", "visible"), ("private", "hidden"), ("protected", "protect")],
)
def test_list_posts_maps_visibility_to_server_vocabulary(tool_value, server_value):
    seen = {}

    def handler(req: httpx.Request):
        seen.update(req.url.params)
        return httpx.Response(200, json={"items": []})

    with _client(handler) as c:
        c.list_posts(visibility=tool_value)
    assert seen["visibility"] == server_value


def test_list_posts_rejects_unknown_filter_values():
    with _client(lambda req: httpx.Response(200, json={"items": []})) as c:
        with pytest.raises(ValueError):
            c.list_posts(visibility="PRIVATE")
        with pytest.raises(ValueError):
            c.list_posts(search_type="all")


def test_get_autosave_unwraps_entry():
    wrapped = {
        "autosavedEntry": {"title": "t", "content": "<p>x</p>", "tags": "a", "categoryId": 0}
    }
    with _client(lambda req: httpx.Response(200, json=wrapped)) as c:
        assert c.get_autosave()["title"] == "t"
    with _client(lambda req: httpx.Response(200, json={"autosavedEntry": None})) as c:
        assert c.get_autosave() is None
