---
name: remarkable-pdf
description: Guidelines for producing clean, readable PDFs laid out for the reMarkable Paper Pro (e-ink) — device-correct page geometry, e-ink typography, KaTeX math, and heading bookmarks. Use whenever a project needs to generate a reMarkable / e-reader–friendly PDF from Markdown or HTML, or asks about reMarkable page size, margins, fonts, math rendering, or bookmarks. Pure guidance — apply it with the project's own tooling.
---

# Making a good PDF for the reMarkable Paper Pro

This is a **guidelines** skill — knowledge, not a program. It tells you how to lay out and
render a PDF that reads well on the reMarkable Paper Pro e-ink screen. Apply it with whatever
the host project already uses (a headless browser, a Markdown/HTML pipeline, a templating
layer). The reference recipe near the end is the canonical way; adapt it to the stack.

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
- **Clear headings** — they become the navigation outline (below).

## Math — use KaTeX, not MathJax-SVG

Write `$…$` (inline) and `$$…$$` (display) and render with **KaTeX**. KaTeX gives true LaTeX
weight; MathJax's SVG output prints visibly **heavier/bold** and looks wrong next to body text.
Stick to KaTeX-supported LaTeX (a large subset); render unsupported macros in red rather than
failing the build (`throwOnError:false`).

## Bookmarks (navigation matters on e-ink)

E-ink has no fast scroll, so a tap-to-navigate outline is essential. Build a **nested PDF
outline from the heading hierarchy** (H1 → H2 → H3 …). Keep headings meaningful.

## Reference render recipe

Canonical pipeline (swap any stage for the project's own tools):

1. Content (Markdown/HTML) → an HTML body. (For Markdown, a parser like `marked`; protect
   `$…$`/`$$…$$` from the parser, and **HTML-escape math text** so `<`, `>`, `&` inside
   formulas don't break the DOM.)
2. Wrap it in an HTML document with the reMarkable CSS and KaTeX.
3. Print to PDF with headless Chrome.
4. Add the heading→page bookmark outline.

**CSS essentials** (substitute `«accent»`, `«font»`):

```css
@page { size: 179.6mm 239.6mm; margin: 13mm 12mm 15mm; }
body  { font: 11.5pt/1.55 «font»; color:#111418; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
h1 { font-size:1.5em; padding-bottom:5pt; border-bottom:1.5pt solid «accent»; page-break-after:avoid; }
h2 { font-size:1.22em; padding-left:7pt; border-left:3pt solid «accent»; page-break-after:avoid; }
p  { margin:0 0 7pt; text-align:justify; hyphens:auto; -webkit-hyphens:auto; }
table, pre, .katex-display { page-break-inside:avoid; }
.katex { font-size:1.05em; }
```

**KaTeX in the page** (vendor the files locally for offline, repeatable builds — loading from a
CDN can lose a race with the print timer and leave raw `$…$`):

```html
<link rel="stylesheet" href="katex/katex.min.css">
<script defer src="katex/katex.min.js"></script>
<script defer src="katex/contrib/auto-render.min.js"></script>
<script>
  addEventListener('load', () => {
    renderMathInElement(document.body, {
      delimiters: [{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},
                   {left:'\\[',right:'\\]',display:true},{left:'\\(',right:'\\)',display:false}],
      throwOnError: false
    });
    document.fonts.ready.then(() => { document.title = 'READY'; });  // fonts loaded before print
  });
</script>
```

**Print with headless Chrome** (the flags matter — see Gotchas):

```bash
google-chrome --headless=new --no-sandbox --disable-gpu \
  --no-pdf-header-footer --run-all-compositor-stages-before-draw \
  --password-store=basic --use-mock-keychain \
  --no-first-run --no-default-browser-check --disable-dev-shm-usage \
  --virtual-time-budget=120000 \
  --print-to-pdf=out.pdf "file://$PWD/doc.html" < /dev/null
```

**Bookmarks:** tag each heading with a unique, invisible marker (e.g. a tiny white
`<span>token</span>`), render, then find which page each token lands on and write a nested
outline. Poppler's `pdftotext` (split output on `\f` page breaks) is fast for the page scan;
`pypdf` can both read pages and write the outline (`add_outline_item(title, page, parent=…)`).

## Verify the output

- **No raw `$` or `\frac`/`\partial`** in the extracted PDF text → math actually rendered.
- **Bookmark tree mirrors the headings.**
- **Math weight matches body text at ≥200 DPI** (low-DPI previews fake "bold" — see Gotchas).
- Tables, figures, and equations are not clipped or split.

## Gotchas (hard-won)

- **MathJax-SVG prints bold/heavy.** Use KaTeX. (Same math, much lighter glyphs.)
- **Headless Chrome hangs with `tcsetattr: Inappropriate ioctl for device`.** It's the OS
  keyring on startup: the secret service spawns `pinentry`, which grabs a TTY and blocks until
  the timeout — looking like an endlessly slow render. Fix: `--password-store=basic
  --use-mock-keychain` and run with **stdin detached** (`< /dev/null`).
- **Low-DPI previews exaggerate weight.** Serif math looks "bold" below ~150 DPI; judge at
  ≥200 DPI or on-device (229 PPI). It is not actually bold.
- **`--virtual-time-budget` is a safety ceiling, not the render time.** A CPU-bound render
  prints when it signals done, regardless of the budget (a tiny budget renders the same doc
  just as fast). Slowness comes from real work — Chrome rasterising a big doc and the
  page-by-page bookmark scan — so give long renders a generous command timeout, don't shrink
  the budget.
- **`<`/`>`/`&` inside math break the DOM** if injected as raw HTML. HTML-escape math text;
  the browser decodes it back to literals for KaTeX.

## Supported agents

Works with any agent that supports the [agent skills spec](https://agentskills.io): Claude
Code, GitHub Copilot, Cursor, Windsurf, and more.
