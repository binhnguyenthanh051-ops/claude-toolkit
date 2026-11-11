# Changelog

All notable changes, per plugin. Versions follow [semantic versioning](https://semver.org); a
plugin's `version` in its `plugin.json` is bumped on every release, or users don't receive it.

## figure-docs

### 0.1.0 · 2026-11-11

- `md-to-html-doc`: figure-led Markdown → report-style HTML. Warm light/dark theme, numbered figures
  and tables, contents sidebar, `key`/`hot` box emphasis in Mermaid figures, A4 print style.
- `md-to-claude-doc`: figure-led Markdown → Claude Doc, with re-sync after the Markdown changes.
- Document author from `--author`, `~/.claude/figure-docs.toml` or `git config user.name`; a
  "Rendered with figure-docs" credit line, removable with `--no-credit`.
- Links that climb above the repo root are kept as written instead of being rewritten.
- `STYLE.md`: the figure-led style guide both skills follow.
