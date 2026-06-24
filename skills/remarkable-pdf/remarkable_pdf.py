#!/usr/bin/env python3
"""
remarkable_pdf.py — render content into a reMarkable Paper Pro–optimised PDF.

Content-agnostic and style-parametrised. Feed it Markdown or HTML — a file, several
files, a folder, or stdin — and it produces a PDF sized for the Paper Pro e-ink
screen with nested bookmarks from the heading structure. Nothing about the look is
baked in: accent colour, fonts and size are all flags, so the same layout can be
reused across unrelated projects.

Engine: headless Chromium (marked.js + KaTeX, vendored next to this file) + pypdf.
Works offline; assets and pypdf are bundled in ./assets and ./vendor.

Usage:
    remarkable_pdf.py report.md
    remarkable_pdf.py page.html -o page.pdf
    some_app --emit-markdown | remarkable_pdf.py - -o out.pdf
    remarkable_pdf.py docs/ --accent "#0a7" --font "Georgia, serif" --font-size 12

Style (default to neutral; pick per project / ask the user):
    --accent HEX        accent for rules & headings   (default #334155)
    --ink HEX           body text colour              (default #111418)
    --font CSS          body font-family stack        (default system sans)
    --mono CSS          code font-family stack        (default system mono)
    --font-size N       base size in pt               (default 11.5)
    --font-css URL      extra stylesheet link (e.g. a web-font CSS URL)

Layout:
    --page WxH          page size in mm   (default 179.6x239.6 — Paper Pro portrait)
    --margin "T S B"    @page margin      (default "13mm 12mm 15mm")
    --landscape
    --break-level N     start a new page before every heading ≤ N (default 0 = flow)

Other:
    --bookmark-depth N  outline depth from headings (default 3; 0 = none)
    --stdin-format md|html   how to read stdin (default md)
    --title TEXT
    -o, --out FILE
    --keep-html
"""

import argparse
import html as htmllib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSET_DIR = HERE / "assets"
DEFAULT_PAGE = "179.6x239.6"          # Paper Pro portrait, 1620×2160 px @ 229 PPI
DEFAULT_MARGIN = "13mm 12mm 15mm"
DEFAULT_ACCENT = "#334155"
DEFAULT_INK = "#111418"
DEFAULT_FONT = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
DEFAULT_MONO = "ui-monospace,'DejaVu Sans Mono',Menlo,Consolas,monospace"


def die(msg):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


# --- assets & optional pypdf -------------------------------------------------

def asset_url(rel, cdn):
    p = ASSET_DIR / rel
    return p.as_uri() if p.is_file() else cdn


MARKED_URL = asset_url("marked.min.js", "https://cdn.jsdelivr.net/npm/marked/marked.min.js")
KATEX_CSS_URL = asset_url("katex/katex.min.css", "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css")
KATEX_JS_URL = asset_url("katex/katex.min.js", "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js")
KATEX_AR_URL = asset_url("katex/contrib/auto-render.min.js",
                         "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js")


def load_pypdf():
    for cand in (HERE / "vendor",
                 Path(os.environ["REMARKABLE_PDF_LIBS"]) if os.environ.get("REMARKABLE_PDF_LIBS") else None):
        if cand and (cand / "pypdf").is_dir() and str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
    try:
        import pypdf  # noqa
        return pypdf
    except Exception:
        return None


def find_chrome():
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
              "microsoft-edge", "chrome"):
        p = shutil.which(n)
        if p:
            return p
    die("Не найден Chromium-браузер (google-chrome / chromium / edge).")


# --- content prep ------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_TOKN = [0]


def _token():
    _TOKN[0] += 1
    return f"@@BK{_TOKN[0]:04d}@@"


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def _plain(s):
    """Strip md/html/latex decoration from a heading for a clean bookmark label."""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\$[^$]*\$", "", s)
    s = re.sub(r"[*_`#]+", "", s)
    s = re.sub(r"\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]", lambda m: (m.group(2) or m.group(1)), s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return s.strip()


def clean_md(md):
    """Convert Obsidian wiki-links to «text» and tidy stray punctuation (math/code safe)."""
    stash = []

    def keep(m):
        stash.append(m.group(0))
        return f"\x00{len(stash) - 1}\x00"

    md = re.sub(r"```.*?```", keep, md, flags=re.S)
    md = re.sub(r"`[^`]*`", keep, md)
    md = re.sub(r"\$\$.*?\$\$", keep, md, flags=re.S)
    md = re.sub(r"(?<!\\)\$[^\n$]*?\$", keep, md)

    def wl(m):
        inner = m.group(1).strip()
        if "|" in inner:
            disp = inner.split("|", 1)[1].strip()
        else:
            disp = inner
            if "#" in disp:
                h, _, t = disp.partition("#")
                disp = f"{h.strip()} › {t.strip()}" if h.strip() else t.strip()
        return f"«{disp}»"
    md = re.sub(r"\[\[([^\[\]]+?)\]\]", wl, md)
    md = re.sub(r"[ \t]+([,;.])", r"\1", md)
    md = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], md)
    return md


def mark_md_headings(md, depth):
    """Inject invisible bookmark markers into ATX headings; return (md, entries)."""
    out, entries, in_code = [], [], False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        m = HEADING_RE.match(line) if not in_code else None
        if m and len(m.group(1)) <= depth:
            lvl = len(m.group(1))
            tok = _token()
            out.append(f'{m.group(1)} <span class="bm">{tok}</span>{m.group(2)}')
            entries.append((lvl - 1, _plain(m.group(2)), tok))
        else:
            out.append(line)
    return "\n".join(out), entries


def mark_html_headings(htmltext, depth):
    entries = []

    def repl(m):
        lvl = int(m.group(1))
        if lvl > depth:
            return m.group(0)
        tok = _token()
        entries.append((lvl - 1, _plain(m.group(3)), tok))
        return f'<h{lvl}{m.group(2)}><span class="bm">{tok}</span>{m.group(3)}'
    out = re.sub(r"<h([1-6])((?:\s[^>]*)?)>(.*?)(?=</h\1>)", repl, htmltext, flags=re.S | re.I)
    return out, entries


def read_block(path, depth):
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".html", ".htm"):
        m = re.search(r"<body[^>]*>(.*?)</body>", raw, re.S | re.I)
        body = m.group(1) if m else raw
        body, entries = mark_html_headings(body, depth)
        return {"type": "html", "content": body}, entries
    raw = re.sub(r"^---\n.*?\n---\n", "", raw, count=1, flags=re.S)
    md, entries = mark_md_headings(clean_md(raw), depth)
    return {"type": "md", "content": md}, entries


def gather(inputs, depth, stdin_format):
    blocks, outline = [], []
    if not inputs or inputs == ["-"]:
        text = sys.stdin.read()
        if stdin_format == "html":
            body, entries = mark_html_headings(text, depth)
            blocks.append({"type": "html", "content": body})
        else:
            md, entries = mark_md_headings(clean_md(text), depth)
            blocks.append({"type": "md", "content": md})
        outline += entries
        return blocks, outline
    files = []
    for s in inputs:
        p = Path(s)
        if p.is_dir():
            files += sorted((f for f in p.rglob("*") if f.suffix.lower() in (".md", ".html", ".htm")
                             and f.stat().st_size > 0),
                            key=lambda x: natural_key(str(x.relative_to(p))))
        elif p.is_file():
            files.append(p)
        else:
            die(f"Не найдено: {p}")
    if not files:
        die("Не найдено ни одного .md/.html файла.")
    for f in files:
        block, entries = read_block(f, depth)
        blocks.append(block)
        outline += entries
    return blocks, outline


# --- HTML --------------------------------------------------------------------

CSS_TEMPLATE = """
@page { size: @W@mm @H@mm; margin: @MARGIN@; }
* { box-sizing:border-box; }
html,body { margin:0; padding:0; }
body { font-family:@FONT@; font-size:@FS@pt; line-height:1.55; font-weight:400;
  color:@INK@; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.doc-body > :first-child { margin-top:0; }
h1,h2,h3,h4,h5,h6 { font-family:@FONT@; font-weight:600; line-height:1.25;
  page-break-after:avoid; color:@INK@; }
h1 { font-size:1.5em; margin:0 0 9pt; padding-bottom:5pt; border-bottom:1.5pt solid @ACCENT@; }
h2 { font-size:1.22em; margin:14pt 0 5pt; border-left:3pt solid @ACCENT@; padding-left:7pt; }
h3 { font-size:1.06em; margin:11pt 0 4pt; }
h4,h5,h6 { font-size:0.96em; margin:9pt 0 4pt; color:#3f4756; }
p { margin:0 0 7pt; text-align:justify; hyphens:auto; -webkit-hyphens:auto; }
ul,ol { margin:6pt 0; padding-left:20pt; }
li { margin:3pt 0; }
a { color:@ACCENT@; text-decoration:none; }
strong,b { font-weight:600; }
blockquote { margin:8pt 0; padding:4pt 11pt; border-left:3pt solid @ACCENT@;
  background:#f5f5f7; color:#333; }
blockquote p { margin:0; }
code { font-family:@MONO@; font-size:0.85em; background:#f0f0f3; padding:0 3px; border-radius:3px; }
pre { font-family:@MONO@; font-size:0.82em; line-height:1.4; background:#f5f5f7;
  border:0.5pt solid #cfcfd6; border-radius:4px; padding:7pt 9pt; white-space:pre-wrap;
  word-wrap:break-word; page-break-inside:avoid; }
pre code { background:none; padding:0; }
table { width:100%; border-collapse:collapse; font-size:0.86em; margin:9pt 0;
  table-layout:auto; page-break-inside:avoid; }
th,td { border:0.5pt solid #9a9aa3; padding:3pt 6pt; text-align:left; word-break:break-word; }
th { background:#ededf2; }
img { max-width:100%; height:auto; }
hr { border:none; border-top:0.5pt solid #c7c7d2; margin:12pt 0; }
.katex { color:@INK@; font-size:1.05em; }
.katex-display { margin:9pt 0 !important; page-break-inside:avoid; overflow-x:auto; overflow-y:hidden; }
.katex-display > .katex { max-width:100%; }
.bm { position:absolute; color:#fff; font-size:5px; }
"""

PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>@TITLE@</title>
@FONTCSS@
<style>@CSS@</style>
<link rel="stylesheet" href="@KATEX_CSS@">
<script src="@MARKED@"></script>
<script defer src="@KATEX_JS@"></script>
<script defer src="@KATEX_AR@"></script>
</head>
<body>
<div class="doc-body" id="doc"></div>
<script>
const BLOCKS = @BLOCKS@;
const BREAK = @BREAK@;
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
(function(){
  const root = document.getElementById('doc');
  if (window.marked && marked.setOptions) marked.setOptions({gfm:true, breaks:false});
  function renderMd(md){
    if(!(window.marked && marked.parse)) return esc(md);
    const st=[];
    md = md.replace(/\$\$([\s\S]+?)\$\$/g, m=>{st.push(m); return '@@M'+(st.length-1)+'@@';});
    md = md.replace(/(?<!\\)\$([^\n$]+?)\$/g, m=>{st.push(m); return '@@M'+(st.length-1)+'@@';});
    let out = marked.parse(md);
    return out.replace(/@@M(\d+)@@/g, (_,i)=>esc(st[+i]));   // escape so <,>,& in math don't break the DOM
  }
  BLOCKS.forEach(b => root.insertAdjacentHTML('beforeend', b.type==='md' ? renderMd(b.content) : b.content));
  if (BREAK > 0){
    const sel = Array.from({length:BREAK}, (_,i)=>'.doc-body h'+(i+1)).join(',');
    let first = true;
    document.querySelectorAll(sel).forEach(h => { if(first){first=false;} else {h.style.pageBreakBefore='always';} });
  }
  function typeset(){
    if(!window.renderMathInElement){ setTimeout(typeset,100); return; }
    try{
      renderMathInElement(document.body, {
        delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},
                    {left:'\\[',right:'\\]',display:true},{left:'\\(',right:'\\)',display:false}],
        throwOnError:false, errorColor:'#cc0000'
      });
    }catch(e){}
    var fr=(document.fonts&&document.fonts.ready)?document.fonts.ready:Promise.resolve();
    fr.then(()=>{document.title='READY'; window.__done=true;}).catch(()=>{document.title='READY'; window.__done=true;});
  }
  if(document.readyState==='complete') typeset(); else window.addEventListener('load', typeset);
})();
</script>
</body>
</html>"""


def build_html(blocks, title, style):
    css = CSS_TEMPLATE
    for k, v in style["css"].items():
        css = css.replace(k, v)
    fontcss = f'<link rel="stylesheet" href="{style["font_css"]}">' if style.get("font_css") else ""
    page = PAGE_TEMPLATE
    repl = {
        "@TITLE@": htmllib.escape(title), "@CSS@": css, "@FONTCSS@": fontcss,
        "@KATEX_CSS@": KATEX_CSS_URL, "@MARKED@": MARKED_URL,
        "@KATEX_JS@": KATEX_JS_URL, "@KATEX_AR@": KATEX_AR_URL,
        "@BLOCKS@": json.dumps(blocks, ensure_ascii=False).replace("</", "<\\/"),
        "@BREAK@": str(style["break_level"]),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    return page


# --- render & bookmarks ------------------------------------------------------

def chrome_print(chrome, html_path, pdf_path, budget_ms):
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                        f"--user-data-dir={prof}", f"--virtual-time-budget={budget_ms}",
                        f"--print-to-pdf={pdf_path}", f"file://{html_path}"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _page_texts(src, reader, npages):
    """Per-page text for locating heading tokens. Prefer poppler's `pdftotext` (C — far
    faster than pypdf's pure-Python extraction, the slowest part on big docs); fall back to
    pypdf if it isn't installed or the page count doesn't line up."""
    exe = shutil.which("pdftotext")
    if exe:
        try:
            out = subprocess.run([exe, "-q", "-enc", "UTF-8", src, "-"],
                                 capture_output=True, encoding="utf-8", errors="replace",
                                 timeout=180).stdout
            parts = out.split("\f")
            if parts and parts[-1] == "":
                parts.pop()
            if len(parts) == npages:
                return parts
        except Exception:
            pass
    texts = []
    for pg in reader.pages:
        try:
            texts.append(pg.extract_text() or "")
        except Exception:
            texts.append("")
    return texts


def add_bookmarks(pypdf, src, dst, outline):
    reader = pypdf.PdfReader(src)
    npages = len(reader.pages)
    texts = _page_texts(src, reader, npages)

    def page_from(tok, start):
        for i in range(start, npages):
            if tok in texts[i]:
                return i
        return None

    writer = pypdf.PdfWriter(clone_from=reader)   # cheap clone, not a page-by-page append
    parents, last, missing = {}, 0, 0
    for level, label, tok in outline:
        pg = page_from(tok, last)                  # headings are in order → pages non-decreasing
        if pg is None:
            pg = page_from(tok, 0)                 # …but be safe if a token sits earlier
        if pg is None:
            pg, missing = last, missing + 1
        else:
            last = pg
        parent = parents.get(level - 1) if level > 0 else None
        item = writer.add_outline_item(label or "—", pg, parent=parent)
        parents[level] = item
        for l in [k for k in parents if k > level]:
            del parents[l]
    with open(dst, "wb") as fh:
        writer.write(fh)
    if missing:
        print(f"⚠️  {missing} закладок не привязаны к странице.")


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Markdown/HTML → reMarkable Paper Pro PDF")
    ap.add_argument("inputs", nargs="*", help=".md/.html files, folders, or - for stdin")
    ap.add_argument("--accent", default=DEFAULT_ACCENT)
    ap.add_argument("--ink", default=DEFAULT_INK)
    ap.add_argument("--font", default=DEFAULT_FONT)
    ap.add_argument("--mono", default=DEFAULT_MONO)
    ap.add_argument("--font-size", type=float, default=11.5)
    ap.add_argument("--font-css", default="")
    ap.add_argument("--page", default=DEFAULT_PAGE)
    ap.add_argument("--margin", default=DEFAULT_MARGIN)
    ap.add_argument("--landscape", action="store_true")
    ap.add_argument("--break-level", type=int, default=0)
    ap.add_argument("--bookmark-depth", type=int, default=3)
    ap.add_argument("--stdin-format", choices=["md", "html"], default="md")
    ap.add_argument("--title")
    ap.add_argument("-o", "--out")
    ap.add_argument("--keep-html", action="store_true")
    args = ap.parse_args()

    try:
        w, h = (float(x) for x in args.page.lower().split("x"))
    except Exception:
        die("--page должен быть WxH, напр. 179.6x239.6")
    if args.landscape:
        w, h = h, w

    chrome = find_chrome()
    blocks, outline = gather(args.inputs, max(0, args.bookmark_depth), args.stdin_format)

    title = args.title or (outline[0][1] if outline else
                           (Path(args.inputs[0]).stem if args.inputs and args.inputs != ["-"] else "Document"))
    if args.out:
        out_pdf = Path(args.out)
    elif args.inputs and args.inputs != ["-"]:
        first = Path(args.inputs[0])
        out_pdf = (first / f"{first.name}.pdf") if first.is_dir() else first.with_suffix(".pdf")
    else:
        out_pdf = Path.cwd() / "document.pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    style = {
        "css": {"@W@": f"{w:g}", "@H@": f"{h:g}", "@MARGIN@": args.margin,
                "@ACCENT@": args.accent, "@INK@": args.ink, "@FONT@": args.font,
                "@MONO@": args.mono, "@FS@": f"{args.font_size:g}"},
        "font_css": args.font_css, "break_level": max(0, args.break_level),
    }
    html_doc = build_html(blocks, title, style)

    print(f"📖 Блоков: {len(blocks)} | закладок: {len(outline)} → {out_pdf}")
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "doc.html"
        hp.write_text(html_doc, encoding="utf-8")
        if args.keep_html:
            kept = out_pdf.with_suffix(".debug.html")
            kept.write_text(html_doc, encoding="utf-8")
            print(f"   HTML: {kept}")
        raw = Path(td) / "raw.pdf"
        # Safety ceiling only — NOT the render time. The render is CPU-bound, so Chrome's
        # virtual clock stays frozen during it and the page prints when it signals done, not
        # when this budget elapses (a 5 s budget renders the same doc just as fast). Wall time
        # is the real render + bookmark work; that's what makes big docs slow, not this number.
        budget = 120000
        print(f"🖨️  Рендеринг (Chrome, лимит {budget // 1000} с)…")
        chrome_print(chrome, hp, raw, budget)
        if not raw.exists() or raw.stat().st_size == 0:
            die("Chrome не создал PDF.")
        pypdf = load_pypdf() if (outline and args.bookmark_depth > 0) else None
        if pypdf:
            print("🔖 Закладки…")
            add_bookmarks(pypdf, str(raw), str(out_pdf), outline)
        else:
            if outline and args.bookmark_depth > 0:
                print("ℹ️  pypdf не найден — PDF без закладок.")
            shutil.copyfile(raw, out_pdf)

    print(f"✅ Готово: {out_pdf}  ({out_pdf.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
