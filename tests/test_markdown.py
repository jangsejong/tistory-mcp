import pytest

from tistory_mcp.client import IMAGE_STYLES, build_attachment_ref, build_image_substitution
from tistory_mcp.markdown import render_content

SUB = (
    "[##_Image|kage@KEY1/abc/KEY2/img.png?credential=c&amp;expires=1&amp;signature=s"
    '|CDM|1.3|{"originWidth":300,"originHeight":366,"style":"alignCenter"}_##]'
)


def test_markdown_basic_blocks():
    md = (
        "# 제목\n\n**굵게** ~~취소~~\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "```python\nprint('x')\n```\n"
    )
    html = render_content(md, "markdown")
    assert "<h1>제목</h1>" in html
    assert "<strong>굵게</strong>" in html and "<s>취소</s>" in html
    assert "<table " in html and "<td>1</td>" in html
    assert '<pre><code class="language-python">' in html


def test_markdown_gets_editor_style_attributes():
    md = "문단\n\n## 소제목\n\n### 하위\n\n> 인용\n\n---\n\n- a\n\n1. b\n\n| a |\n|---|\n| 1 |\n"
    html = render_content(md, "markdown")
    assert '<p data-ke-size="size16">문단</p>' in html
    assert '<h2 data-ke-size="size26">' in html and '<h3 data-ke-size="size23">' in html
    assert '<blockquote data-ke-style="style1">' in html
    assert '<hr data-ke-style="style1">' in html
    assert '<ul data-ke-list-type="disc">' in html and '<ol data-ke-list-type="decimal">' in html
    assert '<table style="width:100%" data-ke-align="alignLeft">' in html
    assert "<p>" not in html and "<hr>" not in html


def test_editor_style_keeps_image_substitution_and_skips_html_format():
    html = render_content(f"앞\n\n{SUB}\n\n뒤", "markdown")
    assert SUB in html
    assert render_content("<p>x</p><hr>", "html") == "<p>x</p><hr>"


def test_editor_style_output_survives_html_path_unchanged():
    # sanitize 가 마지막이라, 마크다운 결과를 html 형식으로 다시 보내도(update_post 기본값) 그대로다
    md = "문단\n\n> 인용\n\n---\n\n- a\n  - b\n\n3. c\n\n| x |\n|---|\n| 1 |\n"
    html = render_content(md, "markdown")
    assert render_content(html, "html") == html


def test_numbered_list_with_start_gets_style():
    md = "1. 설치\n\n```bash\npip install x\n```\n\n2. 실행\n"
    html = render_content(md, "markdown")
    assert '<ol data-ke-list-type="decimal">' in html
    assert '<ol start="2" data-ke-list-type="decimal">' in html


def test_nested_bullets_follow_depth():
    html = render_content("- a\n  - b\n    - c\n      - d\n", "markdown")
    kinds = [k for k in ("disc", "circle", "square") if f'data-ke-list-type="{k}"' in html]
    assert kinds == ["disc", "circle", "square"]
    assert html.index('"disc"') < html.index('"circle"') < html.index('"square"')
    mixed = render_content("1. a\n   - b\n", "markdown")
    assert '<ul data-ke-list-type="circle">' in mixed  # ol 안의 ul 도 2단계


def test_editor_style_leaves_code_and_attributed_raw_html():
    html = render_content(
        '```html\n<p>x</p>\n<hr>\n```\n\n<ol type="a"><li>y</li></ol>\n', "markdown"
    )
    assert "&lt;p&gt;x&lt;/p&gt;" in html and "&lt;hr&gt;" in html
    assert '<ol type="a"><li>y</li></ol>' in html


def test_dangerous_html_is_stripped():
    md = '텍스트 <script>alert(1)</script> <a href="javascript:x()" onclick="y()">링크</a>'
    html = render_content(md, "markdown")
    assert "<script" not in html and "onclick" not in html and "javascript:" not in html
    assert "링크" in html


def test_image_substitution_preserved_verbatim():
    md = f"앞 문단\n\n{SUB}\n\n뒤 문단"
    html = render_content(md, "markdown")
    assert SUB in html  # &amp; 와 | _ 가 전혀 변형되지 않아야 attachments 와 글자 단위 일치


def test_html_format_only_sanitizes():
    src = f'<p style="color:red;position:absolute">x</p>{SUB}<iframe src="https://youtu.be/x"></iframe>'
    html = render_content(src, "html")
    assert SUB in html
    assert "color" in html and "position" not in html
    assert "<iframe" in html


def test_invalid_format():
    with pytest.raises(ValueError):
        render_content("x", "rst")


# ── image substitution hardening ─────────────────────────────────────────────
BAD_SUBS = [
    "[##_Image|<script>alert(1)</script>_##]",
    '[##_Image|kage@K/a.png|CDM|1.3|{"x":"\\"><img src=x onerror=alert(1)>"}_##]',
    '[##_Image|\n<iframe src="javascript:alert(1)">\n<svg onload=alert(1)>_##]',
    "[##_Image|https://evil.example/x.png|CDM|1.3|"
    '{"originWidth":1,"originHeight":1,"style":"alignCenter"}_##]',
    '[##_Image|kage@K/a.png|CDM|1.3|{"originWidth":1,"originHeight":1,"style":"evil"}_##]',
    "[##_Image|kage@K/a.png|CDM|1.3|"
    '{"originWidth":1,"originHeight":1,"style":"alignCenter","caption":"x"}_##]',
    '[##_Image|kage@K/a".png|CDM|1.3|{"originWidth":1,"originHeight":1,"style":"alignCenter"}_##]',
    "[##_Image|[##_Image|kage@K/a.png|CDM|1.3|"
    '{"originWidth":1,"originHeight":1,"style":"alignCenter"}_##]',
]


@pytest.mark.parametrize("fmt", ["markdown", "html"])
@pytest.mark.parametrize("bad", BAD_SUBS)
def test_malformed_image_substitution_is_rejected(bad, fmt):
    # The inner text of a substitution is restored after sanitizing, so anything that is not
    # exactly what tistory_upload_image produced must be rejected, never passed through.
    with pytest.raises(ValueError, match="치환자"):
        render_content(f"앞\n\n{bad}\n\n뒤", fmt)


@pytest.mark.parametrize("style", IMAGE_STYLES)
@pytest.mark.parametrize("fmt", ["markdown", "html"])
def test_generated_substitution_roundtrips(style, fmt):
    upload = {
        "url": "https://cdn.example/x/한글 이미지.png?credential=a%2Bb&expires=1&signature=s%3D",
        "key": "KEY/abc/DEF",
        "filename": "한글 이미지.png",
    }
    sub = build_image_substitution(build_attachment_ref(upload), 1200, 800, style)
    html = render_content(f"앞 {sub} 뒤\n\n{sub}", fmt)
    assert html.count(sub) == 2


def test_forged_placeholder_is_not_expanded():
    # Placeholders carry a per-call nonce, so a body cannot smuggle one in (e.g. inside an
    # attribute, where the restored quotes would break out of it).
    forged = "TISTORYIMG0123456789abcdefN0X"
    legacy = "TISTORYIMAGEPLACEHOLDER0TISTORYIMAGEPLACEHOLDER"
    html = render_content(f'{SUB}<a href="https://x/{forged}" title="{legacy}">x</a>', "html")
    assert html.count("[##_Image|") == 1
    assert forged in html and legacy in html


def test_code_block_containing_substitution_is_rejected_not_leaked():
    md = f"```\n{BAD_SUBS[0]}\n```\n"
    with pytest.raises(ValueError):
        render_content(md, "markdown")
