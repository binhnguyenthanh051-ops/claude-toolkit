---
name: md-to-claude-doc
description: Convert a figure-led Markdown page (numbered sections, Mermaid figures, captioned tables, code walkthroughs) into a Claude Doc with a fixed house style, or re-sync a doc after its Markdown changed. Use when the user asks to turn a .md file into a Claude Doc, publish it for review, or update the doc from the file.
---

# Markdown → Claude Doc (figure-led house style)

The source of truth is the Markdown file in the repo. The Claude Doc is a **rendered, commentable
copy** for review and sharing. Convert faithfully: same sections, same figures, same numbers, same
order. Never invent, summarise or drop content.

The style both sides follow is `STYLE.md` at the plugin root (two levels up from this skill). If the repo has its own
`docs/style-guide.md`, that file wins.

## 0. Before any docs call

1. Load the docs skill if the client lists one (`anthropic-skills:docs`); otherwise call
   `guide(items=["topic.index"])` once. Follow the server's birth → open → fill contract.
2. Read the whole Markdown file. Get the repo's web URL and commit:
   `git -C <repo> remote get-url origin` (convert `git@github.com:o/r.git` → `https://github.com/o/r`)
   and `git -C <repo> rev-parse --short HEAD`. Note whether the file has uncommitted changes.

## 1. Check the page against the style (report, never silently fix)

List every deviation, then convert anyway:
- no `**Summary.**` paragraph, or no status line under the title
- a section heading that isn't `## N. Title` (end matter such as Glossary and Related is exempt)
- a figure or table with no `**Figure N.**` / `**Table N.**` caption, or numbering out of order
- a Mermaid figure with more than 12 nodes, GitHub `[!NOTE]` alerts, or images with relative paths

## 2. Map each element

| Markdown | Claude Doc |
|---|---|
| `# Title` | the doc name (`container.create.name`) and the `#` title line |
| `**Status:** s · date · scope` | byline = exactly `<?claude block asof?> · <?claude block me?>` (date chip from the status line's date, else today). The status words go into the first line of the lead: `Status: draft for review.` |
| `**Summary.** …` | the lead paragraph, verbatim |
| `## N. Title` | one pending block per section at birth, then one `replace` per section, heading kept with its number |
| ```` ```mermaid ```` block | kept as a ```` ```mermaid ```` block, unchanged |
| `**Figure N.** caption` | the paragraph directly under its figure, unchanged |
| `**Table N.** caption` + pipe table | caption paragraph, then the pipe table, unchanged |
| fenced code (`armasm`, `c`, `toml`…) | the same fenced block, same language tag |
| `> **Note.** …` | the same blockquote |
| relative link `[x](path.md)` | absolute link `https://github.com/<o>/<r>/blob/<branch>/<dir>/<path>` |
| relative image | upload it (`guide(items=["topic.uploads"])`), never a broken path |
| Glossary / Related | an unnumbered `##` section at the end, as written |

Add one last line after the end matter, in the doc only:
`Source: [<path>](<blob URL>) at <short sha>` (+ ` with uncommitted changes` when they exist).

**Optional, only when the user asks for a polished version:** redraw a Mermaid figure as an SVG widget
following `guide(items=["topic.diagram"])`, with the figure's caption as the embed caption. Keep the
same nodes, labels and arrows; say which figures were redrawn.

## 3. Build the doc

1. **Birth** (first docs call): one `batch` creating the doc. The markdown is: title, byline, the lead,
   then `<?claude block sN?>` per numbered section and per end-matter section. Each pending intent is
   `"<N. Title>: <its exhibits, e.g. Figure 3 pipeline + Table 2>"`.
2. **Open** it with `Artifact(action="open", url=<the trailer's link>)` straight away.
3. **Fill** one section per `update` (`replace` its pending block, `"as":"markdown"`), in reading
   order, with a one-line chat note between calls ("now 3. How it works").
4. **Look once:** check each fill's ack. Every pending block must be resolved (`pending_ended`), and every
   Mermaid figure must be a `codeBlock language='mermaid'`. Claude Docs renders those as diagrams
   (confirmed by the owner on 2026-11-10), so no redraw is needed for them.

## 4. Re-sync after the Markdown changes

Read the doc (`view`, `sinceRev` = the last bookmark) and compare it with the file section by section.
Replace only the sections whose Markdown changed, matching them by heading. If a reviewer edited the doc
text, their edit wins: list it for the user to fold back into the Markdown instead of overwriting it.
Update the `Source:` line to the new commit.

## 5. Reply

One line with the doc's link and what was converted (sections, figures, tables), then the deviation
list from step 1, if there was one. Don't recap the content.

## Style tokens (what "well defined" means here)

- One tab per page. The doc name equals the Markdown title.
- Headings keep their numbers: `## 3. How it works`. Sentence case and no emoji, as in the source.
- Every exhibit has a numbered caption, figure captions below, table captions above.
- Prose stays as written: ≤ 3 sentences per paragraph, units on every number.
- The doc is never edited ahead of the Markdown. Changes go into the repo first, then re-sync.
