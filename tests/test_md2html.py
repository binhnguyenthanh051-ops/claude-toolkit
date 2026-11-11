"""Tests for plugins/figure-docs/skills/md-to-html-doc/scripts/md2html.py."""
from pathlib import Path

import pytest

import md2html

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def built(tmp_path):
    """Render both fixture pages into tmp_path/out and return (out_dir, sample_html)."""
    out = tmp_path / "out"
    rc = md2html.main([str(FIX / "sample.md"), str(FIX / "other.md"), "--root", str(FIX),
                       "--out", str(out), "--repo-url", "https://github.com/o/r", "--commit", "abc1234",
                       "--author", "Ada Lovelace", "--author-url", "https://example.com/ada"])
    assert rc == 0
    return out, (out / "sample.html").read_text(encoding="utf-8")


def test_title_status_and_summary(built):
    _, page = built
    assert "<h1>Sample page</h1>" in page
    assert page.count('class="chip"') == 3
    assert 'class="summary"' in page and "The converter keeps every figure" in page


def test_figure_gets_its_caption_and_mermaid_source_is_escaped(built):
    _, page = built
    assert '<figure class="fig" id="figure-1">' in page
    assert '<span class="lbl">Figure 1.</span> The pipeline, two boxes.' in page
    assert 'A[&quot;Input&lt;br/&gt;md&quot;]' in page   # Mermaid reads textContent, so it must be escaped
    assert "class A key" in page


def test_table_caption_group_row_and_escaped_pipes(built):
    _, page = built
    assert '<figure class="tbl" id="table-1">' in page
    assert '<tr class="group">' in page
    assert "<td>a | b</td>" in page
    assert "<code>x|y</code>" in page          # a pipe inside code stays in its cell


def test_numbered_headings_feed_the_contents(built):
    _, page = built
    assert '<h2 id="1-pipeline"><span class="num">1</span>Pipeline</h2>' in page
    assert '<span class="num">D1</span>A decision' in page
    assert page.count('<li class="l2">') == 2 and page.count('<li class="l3">') == 2  # sidebar + inline


def test_assembly_addresses_and_comments_are_marked(built):
    _, page = built
    assert '<span class="ad">10086742</span>' in page
    assert '<span class="cm"> @ push 2 registers</span>' in page


def test_callout_lists_and_inline_escaping(built):
    _, page = built
    assert '<aside class="callout note"><span class="lbl">Note</span>' in page
    assert "<em>item</em>" in page and "<strong>items</strong>" in page
    assert "<code>&lt;raw&gt;</code>" in page


def test_links_between_pages_and_to_the_repo(built):
    out, page = built
    assert 'href="other.html"' in page
    assert 'href="../src/main.c"' in page            # climbs above the root: kept as written
    assert "blob/main/src/main.c" not in page
    assert 'href="sample.html"' in (out / "other.html").read_text(encoding="utf-8")


def test_counts_and_source_line(built):
    _, page = built
    assert "1 figures · 1 tables" in page
    assert '<a href="https://github.com/o/r/blob/main/sample.md">sample.md</a>' in page
    assert "<code>abc1234</code>" in page


def test_author_signature_and_tool_credit(built):
    _, page = built
    assert '<span class="sig"><a href="https://example.com/ada">Ada Lovelace</a></span>' in page
    assert "© " in page and "Ada Lovelace</span></div>" in page
    assert 'Rendered with <a href="https://github.com/binhnguyenthanh051-ops/claude-toolkit">figure-docs</a>' \
        in page
    assert "by Nguyen Thanh Binh" in page


def test_no_author_and_no_credit(tmp_path):
    out = tmp_path / "out"
    md2html.main([str(FIX / "other.md"), "--out", str(out), "--author", "", "--no-credit"])
    page = (out / "other.html").read_text(encoding="utf-8")
    assert 'class="byline"' not in page and 'class="signoff"' not in page
    assert 'class="credit"' not in page


def test_author_comes_from_the_user_config(tmp_path):
    cfg = tmp_path / "figure-docs.toml"
    cfg.write_text('[author]\nname = "Grace Hopper"\nurl = "https://example.com/grace"\n', encoding="utf-8")
    assert md2html.resolve_author(None, None, cfg, tmp_path) == ("Grace Hopper", "https://example.com/grace")
    assert md2html.resolve_author("", None, cfg, tmp_path) == ("", "")


def test_output_is_deterministic(tmp_path):
    args = [str(FIX / "sample.md"), "--author", "", "--commit", "x"]
    md2html.main(args + ["--out", str(tmp_path / "a")])
    md2html.main(args + ["--out", str(tmp_path / "b")])
    assert (tmp_path / "a" / "sample.html").read_bytes() == (tmp_path / "b" / "sample.html").read_bytes()
