from pathlib import Path

from personal_digest.infrastructure.rendering.jinja_renderer import JinjaDigestRenderer


def test_renderer_converts_markdown_to_html() -> None:
    template_dir = Path(__file__).resolve().parents[2] / "templates"
    renderer = JinjaDigestRenderer(template_dir=template_dir)

    html = renderer.render_html("# Title\n\nHello **Digest**", "Digest Subject")

    assert "Digest Subject" in html
    assert "<h1>Title</h1>" in html
    assert "<strong>Digest</strong>" in html

