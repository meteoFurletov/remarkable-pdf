---
name: remarkable-pdf
description: Guidelines for producing clean, readable PDFs laid out for the reMarkable Paper Pro (e-ink) — device-correct page geometry, e-ink typography, KaTeX math, and heading bookmarks. Covers two render engines (WeasyPrint and headless Chrome) and when to use each. Use whenever a project needs to generate a reMarkable / e-reader–friendly PDF from Markdown or HTML, or asks about reMarkable page size, margins, fonts, math, or bookmarks. Pure guidance — apply it with the project's own tooling.
---

# Making a good PDF for the reMarkable Paper Pro

This is a **guidelines** skill — knowledge, not a program. It tells you how to lay out and
render a PDF that reads well on the reMarkable Paper Pro e-ink screen. Apply it with whatever
the host project already uses. The page geometry, typography, math, and bookmark *rules* are
engine-independent; pick an engine in **Rendering** below.

## First — ask the user for the look

The layout is fixed (it matches the device); the *style* is a choice. Unless the user already
said, ask and offer these defaults (all optional):

- **Accent colour** — title rule + section markers. Default a neutral slate `#334155`. Keep it
  calm: e-ink is greyscale-ish, so saturated colours read as mid-grey anyway.
- **Font** — body + headings. Default a clean system sans; **a serif (e.g. Georgia) often
  reads better for long-form on e-ink** — offer both.
- **Base size** — default `11.5pt`; bump to `12–13` for comfort.

## Device geometry (non-negotiable)

- The Paper Pro screen is **1620 × 2160 px @ 229 PPI → a 179.6 × 239.6 mm portrait page.**
  Set the PDF page to exactly that so one page maps 1:1 to the display — no pinch-zoom.
- Margins ≈ **13 mm top / 12 mm sides / 15 mm bottom**; line-height ≈ **1.55**. Air is comfort
  on e-ink.
- Different device or orientation → scale/swap these; everything else below still holds.

## Typography & layout for e-ink

- **High contrast, minimal chrome.** Near-black ink on white. Use the accent only as a thin
  rule/bar. No backlight, so avoid grey body text, faint hairlines, and heavy fills.
- **Justify with hyphenation** for an even greyscale block.
- **Keep blocks whole.** Set `page-break-inside: avoid` on tables, code blocks, and display
  equations so they never split across a page break.
- **Use real `<h1>`–`<h6>` headings** — they become the navigation outline (below), and on
  WeasyPrint they generate bookmarks automatically. If you clean/scrape HTML, keep them as `hN`.

## Math — use KaTeX, not MathJax-SVG

Write `$…$` (inline) and `$$…$$` (display) and render with **KaTeX**. KaTeX gives true LaTeX
weight; MathJax's SVG output prints visibly **heavier/bold** and looks wrong next to body text.
Render unsupported macros in red rather than failing the build (`throwOnError:false`). *How* you
invoke KaTeX depends on the engine (see Rendering).

## Bookmarks (navigation matters on e-ink)

E-ink has no fast scroll, so a tap-to-navigate outline is essential. Build a **nested PDF
outline from the heading hierarchy** (H1 → H2 → H3 …). WeasyPrint does this for free; with
Chrome you add it as a post-process (see Rendering).

## Rendering — pick an engine

The rules above are identical either way; only the engine differs.

| | **WeasyPrint** (pure Python) | **Headless Chrome** (`print-to-pdf`) |
|---|---|---|
| Speed | **seconds** | slower; a browser cold-start (esp. **snap/flatpak Chrome**) can take minutes |
| Robustness | no browser → none of the Chrome gotchas below | hits the keyring/TTY + sandbox gotchas |
| Math | no JS → **pre-render KaTeX to HTML first** | runs JS → **KaTeX auto-renders in-page** |
| Bookmarks | **automatic from `<h1>`–`<h6>`** | add as a post-process (e.g. `pypdf`) |
| Page size / CSS | ✅ excellent `@page` support | ✅ |
| Install | `pip install weasyprint` (+ Pango/cairo libs) | a Chromium-family browser |

**Rule of thumb: default to WeasyPrint** — it's fast and sidesteps the whole class of headless-
Chrome problems. Reach for **Chrome** when the content genuinely needs a JS engine (live KaTeX
without a pre-render step, or JS-driven content).

**Shared CSS essentials** (both engines; substitute `«accent»`, `«font»`):

```css
@page { size: 179.6mm 239.6mm; margin: 13mm 12mm 15mm; }
body  { font: 11.5pt/1.55 «font»; color:#111418; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
h1 { font-size:1.5em; padding-bottom:5pt; border-bottom:1.5pt solid «accent»; page-break-after:avoid; }
h2 { font-size:1.22em; padding-left:7pt; border-left:3pt solid «accent»; page-break-after:avoid; }
p  { margin:0 0 7pt; text-align:justify; hyphens:auto; }
table, pre, .katex-display { page-break-inside:avoid; }
.katex { font-size:1.05em; }
```

### Option A — WeasyPrint (fast, no browser)

```python
from weasyprint import HTML
HTML(string=full_html, base_url=".").write_pdf("out.pdf")  # @page sets the reMarkable size
```

- **Bookmarks are automatic** from `<h1>`–`<h6>`; fine-tune with CSS `bookmark-level` /
  `bookmark-label` if needed.
- **Math:** WeasyPrint runs no JavaScript, so KaTeX's auto-render won't fire. Pre-render it —
  run KaTeX server-side (`katex.renderToString` via Node, or a Python KaTeX binding) to convert
  each `$…$` into static KaTeX HTML, include `katex.min.css` + its fonts, then pass that HTML to
  WeasyPrint. (No pre-render → no math. MathJax/MathML aren't options here.) Expect minor KaTeX
  layout quirks vs a browser; acceptable for most docs.
- Fonts come from the system (fontconfig) or `@font-face` with local files (`base_url` resolves
  relative paths).

### Option B — headless Chrome (full JS fidelity)

Load KaTeX in the page, let it auto-render, then print:

```html
<link rel="stylesheet" href="katex/katex.min.css">
<script defer src="katex/katex.min.js"></script>
<script defer src="katex/contrib/auto-render.min.js"></script>
<script>addEventListener('load',()=>{renderMathInElement(document.body,{delimiters:[
  {left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});
  document.fonts.ready.then(()=>document.title='READY');});</script>
```

```bash
google-chrome --headless=new --no-sandbox --disable-gpu \
  --no-pdf-header-footer --run-all-compositor-stages-before-draw \
  --password-store=basic --use-mock-keychain \
  --no-first-run --no-default-browser-check --disable-dev-shm-usage \
  --virtual-time-budget=120000 \
  --print-to-pdf=out.pdf "file://$PWD/doc.html" < /dev/null
```

- Vendor KaTeX locally — a CDN load can lose the race with the print timer and leave raw `$…$`.
- Protect `$…$`/`$$…$$` from any Markdown parser, and **HTML-escape math text** so `<`/`>`/`&`
  inside formulas don't break the DOM.
- **Bookmarks:** Chrome doesn't emit them. Tag each heading with an invisible unique marker,
  render, find which page each marker lands on (poppler `pdftotext` is fast; `pypdf` also
  works), then write a nested outline with `pypdf` `add_outline_item(title, page, parent=…)`.

## Verify the output

- **No raw `$` or `\frac`/`\partial`** in the extracted PDF text → math actually rendered.
- **Bookmark tree mirrors the headings.**
- **Math weight matches body text at ≥200 DPI** (low-DPI previews fake "bold" — see Gotchas).
- Tables, figures, and equations are not clipped or split.

## Gotchas (hard-won)

- **MathJax-SVG prints bold/heavy.** Use KaTeX. (Same math, much lighter glyphs.)
- **snap/flatpak Chrome cold-starts in minutes.** If a headless render is mysteriously slow,
  that's usually it — use a deb/system Chrome, or just switch to WeasyPrint.
- **Headless Chrome hangs with `tcsetattr: Inappropriate ioctl for device`.** It's the OS
  keyring on startup: the secret service spawns `pinentry`, which grabs a TTY and blocks until
  the timeout. Fix: `--password-store=basic --use-mock-keychain` and **stdin detached**
  (`< /dev/null`). WeasyPrint avoids this entirely.
- **Low-DPI previews exaggerate weight.** Serif math looks "bold" below ~150 DPI; judge at
  ≥200 DPI or on-device (229 PPI). It is not actually bold.
- **`--virtual-time-budget` is a safety ceiling, not the render time.** A CPU-bound Chrome
  render prints when it signals done, regardless of the budget. Slowness is real work, so give
  long renders a generous command timeout — don't shrink the budget.

## Supported agents

Works with any agent that supports the [agent skills spec](https://agentskills.io): Claude
Code, GitHub Copilot, Cursor, Windsurf, and more.
