"""md2html.py: render figure-led Markdown pages as styled, self-contained HTML documents.

Standard library only. Handles the subset the figure-led style guide allows: headings, paragraphs,
pipe tables, fenced code (incl. ```mermaid), blockquotes, lists, inline code/bold/italic/links.

    python md2html.py PAGE.md [PAGE2.md ...] --out DIR [--repo-url URL] [--commit SHA]

Figure-led conventions it understands:
    # Title                         -> document title
    **Status:** a · b · c           -> meta chips under the title
    **Summary.** ...                -> summary panel
    ## N. Title                     -> numbered section, listed in the contents sidebar
    ```mermaid + **Figure N.** ...  -> <figure> with caption
    **Table N.** ... + table        -> <figure> with caption above the table
    > **Note.** / **Limit.**        -> callout
Links to sibling .md pages become .html; other relative links point at the repo URL when given.
"""
from __future__ import annotations

import argparse
import datetime
import html
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
USER_CONFIG = Path.home() / ".claude" / "figure-docs.toml"   # per-user, survives plugin updates
CSS_PATH = HERE.parent / "assets" / "doc.css"
TOOL_NAME = "figure-docs"
TOOL_URL = "https://github.com/binhnguyenthanh051-ops/claude-toolkit"
TOOL_AUTHOR = "Nguyen Thanh Binh"
JS_PATH = HERE.parent / "assets" / "doc.js"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs"

FENCE_RE = re.compile(r"^```\s*([\w+-]*)\s*$")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
CAPTION_RE = re.compile(r"^\*\*(Figure|Table)\s+(\d+)\.\*\*\s*(.*)$", re.S)
CALLOUT_RE = re.compile(r"^\*\*([A-Z][\w ]*)\.\*\*\s*(.*)$", re.S)
NUMBERED_RE = re.compile(r"^(\d+)\.\s+(.*)$")
DECISION_RE = re.compile(r"^(D\d+)\.\s+(.*)$")


# ---------------------------------------------------------------- inline

def slug(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


@dataclass
class LinkMap:
    pages: set[str]              # repo-relative .md paths being converted together
    page_dir: str                # repo-relative directory of the current page
    repo_url: str | None
    branch: str

    def resolve(self, url: str) -> str:
        if re.match(r"^[a-z]+:|^#|^mailto:", url):
            return url
        path, _, frag = url.partition("#")
        target = _norm(f"{self.page_dir}/{path}" if self.page_dir else path)
        if target is None:          # climbs above the root: no safe rewrite, keep it as written
            return url
        if target in self.pages:
            rel = path[:-3] + ".html"
            return rel + (f"#{frag}" if frag else "")
        if self.repo_url:
            return f"{self.repo_url}/blob/{self.branch}/{target}" + (f"#{frag}" if frag else "")
        return url


def _norm(p: str) -> str | None:
    """Normalise a root-relative path; None if it climbs above the root."""
    parts: list[str] = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


def inline(text: str, links: LinkMap) -> str:
    codes: list[str] = []

    def stash(m: re.Match) -> str:
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text, quote=False)
    text = text.replace("&lt;br/&gt;", "<br>").replace("&lt;br&gt;", "<br>")
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: f'<a href="{html.escape(links.resolve(m.group(2)))}">{m.group(1)}</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


# ---------------------------------------------------------------- blocks

@dataclass
class Block:
    kind: str                    # heading, para, code, table, quote, list
    text: str = ""
    level: int = 0
    lang: str = ""
    rows: list[list[str]] = field(default_factory=list)
    items: list[tuple[int, bool, str]] = field(default_factory=list)


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, cur, in_code = [], "", False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur.strip())
    return cells


def parse(md: str) -> list[Block]:
    lines = md.replace("\r\n", "\n").split("\n")
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = FENCE_RE.match(line.strip())
        if m:
            lang, body = m.group(1), []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            blocks.append(Block("code", "\n".join(body), lang=lang))
            i += 1
            continue
        m = HEADING_RE.match(line)
        if m:
            blocks.append(Block("heading", m.group(2).strip(), level=len(m.group(1))))
            i += 1
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = split_row(lines[i])
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            blocks.append(Block("table", rows=rows))
            continue
        if line.lstrip().startswith(">"):
            body = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                body.append(lines[i].lstrip()[1:].strip())
                i += 1
            blocks.append(Block("quote", " ".join(body)))
            continue
        if LIST_RE.match(line):
            items = []
            while i < len(lines) and lines[i].strip():
                lm = LIST_RE.match(lines[i])
                if lm:
                    items.append((len(lm.group(1)), lm.group(2)[0].isdigit(), lm.group(3)))
                elif items:
                    d, o, t = items[-1]
                    items[-1] = (d, o, t + " " + lines[i].strip())
                i += 1
            blocks.append(Block("list", items=items))
            continue
        body = []
        while i < len(lines) and lines[i].strip() and not (
                FENCE_RE.match(lines[i].strip()) or HEADING_RE.match(lines[i])
                or lines[i].lstrip().startswith(("|", ">")) or LIST_RE.match(lines[i])):
            body.append(lines[i].strip())
            i += 1
        blocks.append(Block("para", " ".join(body)))
    return blocks


# ---------------------------------------------------------------- render

ASM_COMMENT = re.compile(r"(\s@\s.*|\s;\s.*)$")


def render_code(b: Block) -> str:
    lang = b.lang or "text"
    body = html.escape(b.text)
    if lang in ("armasm", "asm", "s"):
        out = []
        for ln in body.split("\n"):
            m = re.match(r"^(\s*)([0-9a-f]{6,})(\s+)(.*)$", ln)
            if m:
                rest = ASM_COMMENT.sub(lambda c: f'<span class="cm">{c.group(1)}</span>', m.group(4))
                ln = f'{m.group(1)}<span class="ad">{m.group(2)}</span>{m.group(3)}{rest}'
            out.append(ln)
        body = "\n".join(out)
    elif lang in ("toml", "python", "py", "bash", "sh", "text"):
        body = re.sub(r"(^|\s)(#\s.*)$", r'\1<span class="cm">\2</span>', body, flags=re.M)
    return (f'<div class="code"><span class="lang">{html.escape(lang)}</span>'
            f"<pre><code>{body}</code></pre></div>")


def render_table(b: Block, links: LinkMap) -> str:
    if not b.rows:
        return ""
    head, *rows = b.rows
    th = "".join(f"<th>{inline(c, links)}</th>" for c in head)
    trs = []
    for r in rows:
        if len(r) > 1 and all(not c for c in r[1:]) and r[0].startswith("**"):
            trs.append(f'<tr class="group"><td colspan="{len(head)}">{inline(r[0], links)}</td></tr>')
            continue
        trs.append("<tr>" + "".join(f"<td>{inline(c, links)}</td>" for c in r) + "</tr>")
    return (f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead>'
            f"<tbody>{''.join(trs)}</tbody></table></div>")


def render_list(b: Block, links: LinkMap) -> str:
    ordered = b.items[0][1]
    tag = "ol" if ordered else "ul"
    lis = "".join(f"<li>{inline(t, links)}</li>" for _, _, t in b.items)
    return f"<{tag}>{lis}</{tag}>"


@dataclass
class Page:
    title: str = ""
    meta: list[str] = field(default_factory=list)
    summary: str = ""
    toc: list[tuple[int, str, str, str]] = field(default_factory=list)  # level, num, text, id
    body: list[str] = field(default_factory=list)
    figures: int = 0
    tables: int = 0


def render(blocks: list[Block], links: LinkMap) -> Page:
    page = Page()
    ids: set[str] = set()
    i = 0

    def uid(base: str) -> str:
        s, n = base, 2
        while s in ids:
            s, n = f"{base}-{n}", n + 1
        ids.add(s)
        return s

    def caption_of(idx: int) -> re.Match | None:
        if 0 <= idx < len(blocks) and blocks[idx].kind == "para":
            return CAPTION_RE.match(blocks[idx].text)
        return None

    while i < len(blocks):
        b = blocks[i]
        if b.kind == "heading" and b.level == 1 and not page.title:
            page.title = b.text
            i += 1
            continue
        if b.kind == "para" and b.text.startswith("**Status:**") and not page.meta:
            page.meta = [inline(p.strip(), links) for p in b.text[len("**Status:**"):].split("·")]
            i += 1
            continue
        if b.kind == "para" and b.text.startswith("**Summary.**") and not page.summary:
            page.summary = inline(b.text[len("**Summary.**"):].strip(), links)
            i += 1
            continue
        if b.kind == "heading":
            lvl = min(b.level, 4)
            num, text = "", b.text
            m = NUMBERED_RE.match(text) or (DECISION_RE.match(text) if lvl == 3 else None)
            if m:
                num, text = m.group(1), m.group(2)
            hid = uid(slug(b.text))
            label = f'<span class="num">{html.escape(num)}</span>' if num else ""
            page.body.append(f'<h{lvl} id="{hid}">{label}{inline(text, links)}</h{lvl}>')
            if lvl in (2, 3):
                page.toc.append((lvl, num, inline(text, links), hid))
            i += 1
            continue
        cap_before = caption_of(i) if b.kind == "para" else None
        if cap_before and cap_before.group(1) == "Table" and i + 1 < len(blocks) \
                and blocks[i + 1].kind == "table":
            page.tables += 1
            n, txt = cap_before.group(2), inline(cap_before.group(3), links)
            page.body.append(
                f'<figure class="tbl" id="table-{n}"><figcaption><span class="lbl">Table {n}.</span> '
                f"{txt}</figcaption>{render_table(blocks[i + 1], links)}</figure>")
            i += 2
            continue
        if b.kind == "code" and b.lang == "mermaid":
            cap = caption_of(i + 1)
            inner = f'<pre class="mermaid">{html.escape(b.text)}</pre>'
            if cap and cap.group(1) == "Figure":
                page.figures += 1
                n, txt = cap.group(2), inline(cap.group(3), links)
                page.body.append(f'<figure class="fig" id="figure-{n}"><div class="canvas">{inner}</div>'
                                 f'<figcaption><span class="lbl">Figure {n}.</span> {txt}</figcaption></figure>')
                i += 2
            else:
                page.body.append(f'<figure class="fig"><div class="canvas">{inner}</div></figure>')
                i += 1
            continue
        if b.kind == "code":
            page.body.append(render_code(b))
        elif b.kind == "table":
            page.body.append(render_table(b, links))
        elif b.kind == "list":
            page.body.append(render_list(b, links))
        elif b.kind == "quote":
            m = CALLOUT_RE.match(b.text)
            if m:
                kind = slug(m.group(1))
                page.body.append(f'<aside class="callout {kind}"><span class="lbl">{html.escape(m.group(1))}</span>'
                                 f"{inline(m.group(2), links)}</aside>")
            else:
                page.body.append(f"<blockquote>{inline(b.text, links)}</blockquote>")
        else:
            page.body.append(f"<p>{inline(b.text, links)}</p>")
        i += 1
    return page


def signature(name: str, url: str) -> str:
    n = html.escape(name)
    return f'<a href="{html.escape(url)}">{n}</a>' if url else n


def credit_line() -> str:
    return (f'<div class="credit">Rendered with <a href="{TOOL_URL}">{TOOL_NAME}</a> '
            f'by {html.escape(TOOL_AUTHOR)}</div>')


def document(page: Page, css: str, js: str, source: str, nav: list[tuple[str, str]],
             author: str = "", author_url: str = "", credit: bool = True) -> str:
    chips = "".join(f'<span class="chip">{m}</span>' for m in page.meta)
    sig = signature(author, author_url) if author else ""
    byline = f'<div class="byline"><span class="lbl">Author</span><span class="sig">{sig}</span></div>' if sig else ""
    year = datetime.date.today().year
    signoff = (f'<div class="signoff"><span class="sig">{sig}</span>'
               f'<span class="copy">© {year} {html.escape(author)}</span></div>') if sig else ""
    tail = credit_line() if credit else ""
    toc = "".join(
        f'<li class="l{lvl}"><a href="#{hid}"><span class="tnum">{html.escape(num)}</span>{text}</a></li>'
        for lvl, num, text, hid in page.toc)
    navlinks = "".join(f'<a href="{h}">{html.escape(t)}</a>' for t, h in nav)
    summary = (f'<section class="summary"><span class="lbl">Summary</span><p>{page.summary}</p></section>'
               if page.summary else "")
    toc_inline = (f'<details class="toc-inline"><summary class="lbl">Contents</summary><ol>{toc}</ol></details>'
                  if page.toc else "")
    plain_title = re.sub(r"<[^>]+>", "", page.title)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(plain_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
<header class="topbar"><nav>{navlinks}</nav><button class="theme" type="button" aria-label="Toggle dark mode">◐</button></header>
<div class="layout">
<aside class="toc" aria-label="Contents"><span class="lbl">Contents</span><ol>{toc}</ol></aside>
<main>
<header class="titleblock">
<h1>{page.title}</h1>
<div class="meta">{chips}</div>
{byline}
<div class="counts">{page.figures} figures · {page.tables} tables</div>
</header>
{summary}
{toc_inline}
{chr(10).join(page.body)}
<footer class="source">{signoff}<div>{source}</div>{tail}</footer>
</main>
</div>
<script type="module">
import mermaid from "{MERMAID_URL}";
{js}
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pages", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, help="repo root (default: common parent of the pages)")
    ap.add_argument("--repo-url", help="e.g. https://github.com/owner/repo")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--commit", default="")
    ap.add_argument("--author", help='document author; "" for none (default: user config, then git user.name)')
    ap.add_argument("--author-url", help="link for the author's name (default: user config)")
    ap.add_argument("--config", type=Path, default=USER_CONFIG, help=argparse.SUPPRESS)
    ap.add_argument("--no-credit", action="store_true", help="leave out the 'Rendered with' footer line")
    args = ap.parse_args(argv)

    pages = [p.resolve() for p in args.pages]
    root = args.root.resolve() if args.root else Path(_common(pages))
    author, author_url = resolve_author(args.author, args.author_url, args.config, root)
    rels = {p: p.relative_to(root).as_posix() for p in pages}
    css = CSS_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    titles = {}
    parsed = {}
    for p in pages:
        blocks = parse(p.read_text(encoding="utf-8"))
        parsed[p] = blocks
        t = next((b.text for b in blocks if b.kind == "heading" and b.level == 1), p.stem)
        titles[p] = t
    args.out.mkdir(parents=True, exist_ok=True)
    for p in pages:
        rel = rels[p]
        page_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
        links = LinkMap(set(rels.values()), page_dir, args.repo_url, args.branch)
        page = render(parsed[p], links)
        out_file = args.out / (rel[:-3] + ".html")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        nav = []
        for q in pages:
            target = (args.out / (rels[q][:-3] + ".html"))
            href = Path(_relpath(target, out_file.parent)).as_posix()
            nav.append((re.sub(r"^ADR-\d+:\s*", "", titles[q]) if q != p else titles[q], href))
        src_link = (f'<a href="{args.repo_url}/blob/{args.branch}/{rel}">{html.escape(rel)}</a>'
                    if args.repo_url else html.escape(rel))
        source = f"Source: {src_link}" + (f" at <code>{html.escape(args.commit)}</code>" if args.commit else "")
        out_file.write_text(document(page, css, js, source, nav, author, author_url, not args.no_credit),
                            encoding="utf-8", newline="\n")
        print(f"{rel} -> {out_file}  ({page.figures} figures, {page.tables} tables, "
              f"{len(page.toc)} contents entries)")
    return 0


def resolve_author(name: str | None, url: str | None, config: Path, root: Path) -> tuple[str, str]:
    """Document author: --author, then the user config file, then git user.name. Never the tool's author."""
    cfg = {}
    if config.is_file():
        cfg = tomllib.loads(config.read_text(encoding="utf-8")).get("author", {})
    if name is None:
        name = cfg.get("name") or _git_user(root)
    if url is None:
        url = cfg.get("url", "")
    return name, (url if name else "")


def _git_user(root: Path) -> str:
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(root), "config", "user.name"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _common(paths: list[Path]) -> str:
    import os
    return os.path.commonpath([str(p.parent) for p in paths]) if len(paths) > 1 else str(paths[0].parent)


def _relpath(target: Path, start: Path) -> str:
    import os
    return os.path.relpath(target, start)


if __name__ == "__main__":
    sys.exit(main())
