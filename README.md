# remarkable-pdf

An [agent skill](https://agentskills.io) that renders **Markdown or HTML into a clean PDF
laid out for the reMarkable Paper Pro** (and other e-ink readers).

When installed, your AI agent can turn any content — notes, reports, docs, piped tool output —
into a PDF that's sized to the device screen, with generous margins, high contrast, real LaTeX
math (KaTeX), and tap-to-navigate bookmarks. The look (accent colour, font, size) is chosen
per use, not baked in.

## Install

```bash
npx skills add remarkable-pdf
```

Or directly from this repo:

```bash
npx skills add meteoFurletov/remarkable-pdf
```

Bookmarks use **pypdf** (one line; rendering and math work without it):

```bash
pip install pypdf      # or: pip install -r requirements.txt
```

A Chromium-family browser (`google-chrome` / `chromium` / `microsoft-edge`) must be on `PATH`.

## What it does

| Aspect | Behaviour |
| --- | --- |
| Page | Sized to the Paper Pro screen (179.6 × 239.6 mm @ 229 PPI) — a page fills the display, no pinch-zoom |
| Input | Markdown, HTML, a folder of either, or piped `stdin` |
| Math | Typeset with **KaTeX** (true LaTeX weight — not the heavier MathJax-SVG look) |
| Bookmarks | Nested outline built from the heading hierarchy (H1 → H2 → H3 …) |
| Style | Accent colour, font, size, page — all flags; nothing hardcoded |
| Layout | Generous margins, high contrast, justified text, tables/code/equations kept whole |
| Offline | marked + KaTeX (with fonts) bundled — no runtime network needed |

## Usage

From a clone of this repo (or point at the installed skill directory):

```bash
python3 skills/remarkable-pdf/remarkable_pdf.py report.md
python3 skills/remarkable-pdf/remarkable_pdf.py page.html -o page.pdf
some_app --emit | python3 skills/remarkable-pdf/remarkable_pdf.py - -o out.pdf
python3 skills/remarkable-pdf/remarkable_pdf.py docs/ \
  --accent "#0a7d55" --font "Georgia, serif" --font-size 12
```

**Style** flags: `--accent HEX` · `--ink HEX` · `--font CSS` · `--mono CSS` · `--font-size N` ·
`--font-css URL`.
**Layout**: `--page WxH` (mm) · `--margin "T S B"` · `--landscape` · `--break-level N`.
**Other**: `--bookmark-depth N` · `--stdin-format md|html` · `--title` · `-o/--out` · `--keep-html`.

See [`skills/remarkable-pdf/SKILL.md`](skills/remarkable-pdf/SKILL.md) for the full layout
rules and design rationale (why these margins, why KaTeX, how bookmarks are built, etc.).

## Supported agents

Works with any agent that supports the [agent skills spec](https://agentskills.io):

- Claude Code
- GitHub Copilot
- Cursor
- Windsurf
- and more

## License

[MIT](LICENSE). Bundled assets (marked, KaTeX) keep their own MIT licenses — see
[`skills/remarkable-pdf/assets/THIRD_PARTY.md`](skills/remarkable-pdf/assets/THIRD_PARTY.md).
