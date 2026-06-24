# remarkable-pdf

An [agent skill](https://agentskills.io) that teaches AI assistants **how to produce clean,
readable PDFs for the reMarkable Paper Pro** (and other e-ink readers).

It's **pure guidance** — no bundled program. When installed, your agent applies these rules
with whatever tooling the project already has (a headless browser, a Markdown/HTML pipeline,
etc.) to lay out and render a PDF that maps 1:1 to the device screen, with e-ink-friendly
typography, real LaTeX math, and tap-to-navigate bookmarks.

## Install

```bash
npx skills add remarkable-pdf
```

Or directly from this repo:

```bash
npx skills add meteoFurletov/remarkable-pdf
```

## What it covers

| Topic | Guidance |
| --- | --- |
| Page geometry | Match the Paper Pro screen — 179.6 × 239.6 mm @ 229 PPI — so a page fills the display |
| Typography | Generous margins, high contrast, justified text; minimal accent (no backlight) |
| Math | Use **KaTeX**, not MathJax-SVG (which prints heavier/bold); `$…$` / `$$…$$` |
| Bookmarks | Build a nested PDF outline from the heading hierarchy (H1 → H2 → H3) |
| Render | Two engines — **WeasyPrint** (fast, pure-Python, auto-bookmarks) or **headless Chrome** (full JS/KaTeX) — and when to use each |
| Gotchas | The keyring/TTY hang, low-DPI "fake bold", `--virtual-time-budget` is a ceiling, escaping `<`/`>` in math |

The chosen look (accent colour, font, size) is decided per use — the skill prompts for it.

See [`skills/remarkable-pdf/SKILL.md`](skills/remarkable-pdf/SKILL.md) for the full guidelines,
the CSS skeleton, and the reference render command.

## Supported agents

Works with any agent that supports the [agent skills spec](https://agentskills.io):

- Claude Code
- GitHub Copilot
- Cursor
- Windsurf
- and more

## License

[MIT](LICENSE).
