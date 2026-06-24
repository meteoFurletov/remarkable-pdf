---
name: remarkable-pdf
description: Render Markdown or HTML into a clean, easy-to-read PDF laid out for the reMarkable Paper Pro (e-ink) — correct page size, generous margins, high contrast, KaTeX math, and bookmarks. Content- and project-agnostic; the look (accent colour, font, size) is chosen per use. Use whenever a project needs a nice reMarkable / e-reader PDF from any content, or asks about reMarkable page size, margins, fonts, math rendering, or bookmarks.
---

# reMarkable Paper Pro PDF

A reusable e-ink reading layout plus a small renderer. It does **not** care where the
content comes from — Markdown or HTML, a file, a folder, or piped stdin — so the same
look can be reused across unrelated projects. Styling is parametrised; nothing is baked in.

Bundled in this skill directory (offline-first):

```
remarkable_pdf.py   # the renderer
assets/             # marked.min.js + KaTeX (css/js/auto-render/fonts)
```

Bookmarks use **pypdf** — `pip install pypdf` (one line). The script auto-detects it and
otherwise still produces a valid PDF, just without the outline.

## Before rendering — ask the user for the look

The layout is fixed (it matches the device); the **style is a choice**. Unless the user
already stated preferences, ask them (offer these defaults, all overridable):

- **Accent colour** — used for the title rule and section markers. Default a neutral slate
  `#334155`. (Pick something calm; e-ink is greyscale-ish, so saturated colours read as mid-grey.)
- **Font** — body + headings. Default a system sans; **a serif (e.g. `Georgia, serif`) often
  reads better for long-form on e-ink**. Offer both.
- **Base font size** — default `11.5pt`; bump to `12–13` for comfort.

Then map the answers to flags below. If they don't care, use the defaults.

## Render

Set `SK` to **this skill's own directory** (the folder holding this `SKILL.md`, wherever it
is installed — don't assume a path). Run the renderer with the project as CWD:

```bash
SK="<directory containing this SKILL.md>"

python3 "$SK/remarkable_pdf.py" report.md                       # a Markdown file
python3 "$SK/remarkable_pdf.py" page.html -o page.pdf           # an HTML file
some_app --emit | python3 "$SK/remarkable_pdf.py" - -o out.pdf  # piped stdin (Markdown)
python3 "$SK/remarkable_pdf.py" docs/                           # a folder (md+html, recursive)

# with the user's chosen look:
python3 "$SK/remarkable_pdf.py" report.md \
  --accent "#0a7d55" --font "Georgia, serif" --font-size 12 -o report.pdf
```

Input is Markdown (`.md`, GFM + `$…$`/`$$…$$` math), HTML (`.html`, used as the body), a
folder of those, or `-`/stdin (`--stdin-format md|html`). An app with arbitrary data just
emits Markdown or HTML and pipes it in.

**Flags** — style: `--accent HEX` · `--ink HEX` · `--font CSS` · `--mono CSS` ·
`--font-size N` · `--font-css URL` (to load a web font). Layout: `--page WxH` (mm,
default `179.6x239.6`) · `--margin "T S B"` · `--landscape` · `--break-level N` (new page
before headings ≤ N; 0 = continuous flow). Other: `--bookmark-depth N` (default 3) ·
`--title` · `-o/--out` · `--keep-html`.

Run the Bash tool with the sandbox disabled (`dangerouslyDisableSandbox: true`) if Chrome
is blocked; a Chromium-family browser (`google-chrome`/`chromium`/`edge`) must be on PATH.

**Set a generous command timeout.** Render time is real work, not the Chrome
`--virtual-time-budget` (which is just a safety ceiling — the CPU-bound render finishes
regardless of it). Two costs dominate and grow with document size: (1) Chrome rendering and
rasterising the PDF, and (2) the bookmark pass, where pypdf scans **every page's text** to
place the outline (≈ tens of ms/page; on a 296-page doc it roughly doubled the wall time).
Big docs (many hundreds of pages) can take minutes on a slow machine — so give the Bash call
a high timeout, the maximum (`timeout: 600000` ms) when unsure. A truncated/empty PDF means
the terminal killed it mid-work: re-run with a higher timeout, or pass `--bookmark-depth 0`
to skip the (slowest) bookmark scan.

## The reMarkable layout rules (what makes it read well)

These are the reusable PDF rules — they hold regardless of content:

- **Page = the screen.** Paper Pro is 1620 × 2160 px @ 229 PPI → a 179.6 × 239.6 mm page.
  Matching it means one PDF page fills the display with no pinch-zoom. Only change `--page`
  for a different device.
- **Generous margins** (`13mm 12mm 15mm`) and ~1.55 line-height — air is comfort on e-ink.
- **High contrast, minimal chrome.** Near-black ink on white; the accent is a thin rule/bar
  only. No backlight → avoid grey body text, faint hairlines, and heavy fills.
- **Justified text with hyphenation** for an even greyscale block.
- **Bookmarks instead of scrolling.** The heading hierarchy (H1→H2→H3…) becomes a nested,
  tap-to-navigate outline — essential because e-ink has no fast scroll. Use clear headings.
- **Keep blocks whole.** Tables, code blocks and display equations are `page-break-inside:
  avoid` so they never split across a page break.
- **Math as real type.** Equations are typeset with **KaTeX** (true LaTeX weight). Don't use
  MathJax-SVG here — its glyph paths print visibly heavier/bold. Write `$…$` / `$$…$$`.

## Verify a build

```bash
python3 - "$OUT_PDF" "$SK" <<'PY'
import sys, os
sys.path = [p for p in sys.path if p not in ('', '.')]   # avoid CWD shadowing stdlib
try:
    import pypdf
except ImportError:                                       # fall back to a bundled vendor/ if present
    sys.path.insert(0, os.path.join(sys.argv[2], "vendor")); import pypdf
from pypdf import PdfReader
r = PdfReader(sys.argv[1]); t = "\n".join((p.extract_text() or "") for p in r.pages)
print("pages:", len(r.pages), "| raw $:", t.count("$"),
      "| raw \\frac/\\partial:", t.count("\\frac")+t.count("\\partial"))
def show(o,d=0):
    for it in o: show(it,d+1) if isinstance(it,list) else print("   "*d+"• "+it.title)
show(r.outline)
PY
```

Pass: `raw $ == 0`, no raw `\frac/\partial`, and a bookmark tree mirroring the headings.
Then **rasterise a math page and look at it** (`pdftoppm -png -r 200 -f N -l N "$OUT_PDF"
/tmp/chk` → Read the PNG): equations typeset, weight matches body text, nothing clipped.

## Gotchas

- **Low-DPI previews exaggerate math weight** — serif math looks "bold" below ~150 DPI; judge
  at ≥200 DPI or on-device (229 PPI). It is not actually bold.
- **KaTeX coverage** is a large LaTeX subset; unsupported macros render red rather than
  breaking the build (`throwOnError:false`).
- **pypdf** (bookmarks): `pip install pypdf`. The script auto-detects an installed pypdf (or a
  bundled `vendor/` in self-contained installs) and falls back to a no-bookmarks PDF otherwise.
- **Stray modules:** an inline `python3 - <<'PY'` puts CWD on `sys.path`; a local
  `bisect.py`/`secrets.py` can shadow stdlib — the verify snippet strips CWD.
- Re-vendoring (only if `assets/` is wiped): `marked` from jsdelivr; KaTeX via
  `npm pack katex@0.16.11`, copying `dist/{katex.min.css,katex.min.js,contrib/auto-render.min.js,fonts/*.woff2}`
  into `assets/katex/` (keep `fonts/` beside the CSS).
- Don't commit generated PDFs or assets unless asked.
