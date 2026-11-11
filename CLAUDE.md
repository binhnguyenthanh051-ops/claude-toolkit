# CLAUDE.md — context for Claude Code

`claude-toolkit` is Nguyen Thanh Binh's public collection of general-purpose Claude Code plugins,
packaged as a plugin marketplace (`binh-toolkit`). Design: `docs/adr/ADR-0001-toolkit.md`.

## Rules

1. **General-purpose only.** Nothing that names a specific project, board, bench or person other than
   the toolkit's author. Project-specific skills belong in their project's `.claude/skills/`.
2. **Every release bumps the plugin's `version`** in `plugins/<name>/.claude-plugin/plugin.json`, adds
   a `CHANGELOG.md` entry and a tag `<plugin>--v<x.y.z>`. Without the bump, users never get it.
3. **Plugins are self-contained.** A skill may only reference files inside its plugin directory (the
   plugin is copied into a cache on install).
4. **Scripts use the standard library only** and have tests in `tests/`. Run `python -m pytest -q`
   before handing back; validate manifests with `claude plugin validate .`.
5. **Docs follow the figure-led style** in `plugins/figure-docs/STYLE.md`.
6. **The tool credit stays.** Generated documents carry the "Rendered with … by Nguyen Thanh Binh"
   line by default; the document's own author is always the user's.
