---
name: md-to-html-doc
description: Render figure-led Markdown pages (numbered sections, Mermaid figures, captioned tables, code walkthroughs) as styled, self-contained HTML documents in a warm report style (title block, summary panel, contents sidebar, numbered figures, light/dark, print-to-PDF). Use when the user asks to generate, convert, export or preview a .md page as HTML, or wants a document "in the report style" / "Claude doc style".
---

# Markdown → HTML report

The Markdown is the source of truth; the HTML is generated from it and never edited by hand. One
script does the conversion, deterministically, with only Python's standard library (3.11+):
`scripts/md2html.py` in this skill's base directory, styled by `assets/doc.css` and `assets/doc.js`.

The page style it expects is the figure-led style guide, `STYLE.md` at the plugin root (two levels up
from this skill), or the repo's own `docs/style-guide.md` if it has one.

## 1. Convert

Convert pages that link to each other **in one run**, so links between them become `.html` and the
top bar lists them all. Pass the repo root so links to other repo files go to the web host:

```bash
python "<this skill's base directory>/scripts/md2html.py" docs/idea.md docs/adr/ADR-0001.md --root . --out build/html --repo-url https://github.com/<owner>/<repo> --commit "$(git rev-parse --short HEAD)"
```

- Output keeps the repo layout under `--out`. Write it to a git-ignored folder (`build/`), never
  next to the Markdown.
- `--repo-url`: from `git remote get-url origin` (turn `git@github.com:o/r.git` into
  `https://github.com/o/r`).
- The script prints the figures, tables and contents entries found per page. A caption that isn't
  counted means the page broke a style rule.

## 2. Signature and credit

| Line | Whose | Set by |
|---|---|---|
| "Author · *name*" under the title, signed footer with © year | the **document's** author | `--author` / `--author-url`, else `~/.claude/figure-docs.toml`, else `git config user.name`; `--author ""` for none |
| "Rendered with figure-docs by Nguyen Thanh Binh" in the footer | the **tool's** author | always on; `--no-credit` removes it |

`~/.claude/figure-docs.toml` (outside the plugin, so updates never overwrite it):

```toml
[author]
name = "Your Name"
url = "https://github.com/you"
```

## 3. What it produces

| Markdown | HTML |
|---|---|
| `# Title` | title block |
| `**Status:** a · b · c` | chips under the title (the first one solid) |
| `**Summary.** …` | summary panel |
| `## N. Title`, `### Dn. Title` | numbered headings + contents sidebar that follows the reader |
| ```` ```mermaid ```` + `**Figure N.** …` | figure card with caption below (Mermaid 10.9.1 from a CDN); `class X key` / `class X hot` boxes get the theme's dark / terracotta |
| `**Table N.** …` + pipe table | table card with caption above |
| ```` ```armasm ```` etc. | code card with a language tag; addresses dimmed, `@` comments coloured |
| `> **Note.** …` | callout |

Light and dark themes (system preference plus a remembered toggle), phone-width layout, and an A4
print style: **Print → Save as PDF gives a report**.

## 4. Check before handing over

1. Every Mermaid figure renders. If you can preview the page (a static server via `preview_start`),
   check for "Syntax error" boxes; otherwise say it wasn't checked visually.
2. The printed counts match the Markdown's numbered figures and tables.
3. Report style deviations (a missing caption, an unnumbered section) instead of silently fixing the
   Markdown.

## 5. Hand over

Send the main page with `SendUserFile` (`display: "render"`) and say where the set was written. To
share it as a page, publish it as an Artifact. Don't commit generated HTML unless asked.
