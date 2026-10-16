"""PDF through headless Chromium: the ``engine = "chromium"`` route of ``[build.<profile>.pdf]``.

The document's HTML (the same pandoc + pandoc-crossref pass as the HTML export, so figure and
table numbers match it) is laid out for print and printed by Chromium through Playwright:

* a title page and a table of contents built from ``[build.<profile>.pdf.document]``;
* a page header (logo + company, project, status + revision) and footer (document number,
  issue date, "Page N of M") on every page;
* chapters on new pages, figures and table rows kept whole, table headers repeated, tables
  wider than the text block shrunk to fit;
* every image resolved to a file on disk (cropped of empty margins when
  ``figure_trim_whitespace``), math as MathML -- nothing is fetched from the network;
* the TOC's page numbers from a first print's PDF outline, then printed again.

    [build.pdf]
    outputs = ["pdf"]

    [build.pdf.pdf]
    engine = "chromium"

    [build.pdf.pdf.document]
    company = "Example Engineering"
    logo = "assets/logo.svg"
    project = "Project title"
    title = "Design report"
    document_number = "EX-001"
    revision = "B"
    status = "DRAFT"
    revisions = [
      { rev = "A", date = "2026-01-10", description = "First issue" },
      { rev = "B", date = "2026-02-02", description = "Updated design" },
    ]
"""

from __future__ import annotations

import base64
import glob
import hashlib
import html
import logging
import mimetypes
import os
import pathlib
import re
import shutil
import tempfile
import urllib.parse
from dataclasses import dataclass
from typing import Optional

from paradoc.io.pdf.config import DocumentInfo, PdfExportConfig

logger = logging.getLogger(__name__)

THIS_DIR = pathlib.Path(__file__).parent
PRINT_CSS = THIS_DIR / "print.css"

#: Paper sizes Chromium knows by name, keyed by the (lower-case) name paradoc.toml uses.
_PAPER = {"a3": ("A3", 297, 420), "a4": ("A4", 210, 297), "a5": ("A5", 148, 210), "letter": ("Letter", 216, 279)}
_TABLE_FONT = {
    "tiny": "0.62em",
    "scriptsize": "0.72em",
    "footnotesize": "0.82em",
    "small": "0.9em",
    "normalsize": "1em",
}


@dataclass
class Heading:
    level: int
    number: str
    text: str
    anchor: str


# --- browser -----------------------------------------------------------------------------------


def _browser_candidates() -> list[str]:
    """Chromium builds already on this machine, newest first: Playwright's download cache
    (any revision, so a Playwright upgrade does not force a re-download) and the system's."""
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), str(pathlib.Path.home() / ".cache" / "ms-playwright")]
    if os.name == "nt":
        roots.append(str(pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"))
    patterns = [
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell*",
        "chromium-*/chrome-linux*/chrome",
        "chromium-*/chrome-win*/chrome.exe",
        "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
    ]

    def revision(path: str) -> int:
        m = re.search(r"chromium(?:_headless_shell)?-(\d+)", path)
        return int(m.group(1)) if m else 0

    found = []
    for root in filter(None, roots):
        for pat in patterns:
            found.extend(p for p in glob.glob(os.path.join(root, pat)) if os.path.isfile(p))
    found.sort(key=revision, reverse=True)
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        exe = shutil.which(name)
        if exe:
            found.append(exe)
    return found


def launch_browser(playwright, explicit: Optional[str] = None):
    """A headless Chromium: ``explicit`` (or ``PARADOC_CHROMIUM``) if given, else Playwright's
    own build, else the first build found on the machine."""
    from playwright.sync_api import Error as PlaywrightError

    explicit = explicit or os.environ.get("PARADOC_CHROMIUM", "").strip() or None
    if explicit:
        return playwright.chromium.launch(executable_path=explicit)
    try:
        return playwright.chromium.launch()
    except PlaywrightError as err:
        first_error = err
    for exe in _browser_candidates():
        try:
            browser = playwright.chromium.launch(executable_path=exe)
            logger.info(f"using Chromium at {exe}")
            return browser
        except PlaywrightError:
            continue
    raise RuntimeError(
        "No Chromium for the PDF export: run `playwright install chromium`, or set "
        f"PARADOC_CHROMIUM to a Chromium/Chrome executable. ({first_error})"
    )


# --- html preparation ----------------------------------------------------------------------------

_HEADING_RE = re.compile(r"<h([1-6])((?:\s[^>]*)?)>(.*?)</h\1>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _attr(attrs: str, name: str) -> Optional[str]:
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else None


def _plain(fragment: str) -> str:
    return html.unescape(_TAG_RE.sub("", fragment)).strip()


def number_headings(body: str, max_level: int = 3) -> tuple[str, list[Heading]]:
    """Prefix headings up to ``max_level`` with their section number and list them.

    A level-1 heading's number is its ``data-label`` when pandoc gave it one (chapter "3",
    appendix "B"), else a running count. ``class="unnumbered"`` headings stay unnumbered.
    """
    counters = [0] * 7
    chapter = ""
    chapter_count = 0
    headings: list[Heading] = []
    used: set[str] = set()

    def replace(m: re.Match) -> str:
        nonlocal chapter, chapter_count
        level, attrs, inner = int(m.group(1)), m.group(2) or "", m.group(3)
        anchor = _attr(attrs, "id")
        if not anchor:
            base = re.sub(r"[^a-z0-9]+", "-", _plain(inner).lower()).strip("-") or "section"
            anchor, i = base, 1
            while anchor in used:
                i += 1
                anchor = f"{base}-{i}"
            attrs = f'{attrs} id="{anchor}"'
        used.add(anchor)
        cls = _attr(attrs, "class") or ""
        number = ""
        if "unnumbered" not in cls.split() and level <= max_level:
            if level == 1:
                chapter_count += 1
                chapter = _attr(attrs, "data-label") or str(chapter_count)
                counters[2:] = [0] * 5
                number = chapter
            else:
                counters[level] += 1
                counters[level + 1 :] = [0] * (6 - level)
                parts = [str(counters[i]) for i in range(2, level + 1)]
                number = ".".join([chapter or "0", *parts])
        text = _plain(inner)
        headings.append(Heading(level, number, text, anchor))
        prefix = f'<span class="secno">{html.escape(number)}</span>' if number else ""
        return f"<h{level}{attrs}>{prefix}{inner}</h{level}>"

    return _HEADING_RE.sub(replace, body), headings


_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.S)
_TRIMMABLE = {".png", ".jpg", ".jpeg"}


def resolve_images(
    body: str,
    search_dirs: list[pathlib.Path],
    crop_dir: Optional[pathlib.Path] = None,
    trim_padding: float = 0.04,
) -> tuple[str, list[str]]:
    """Point every local ``<img src>`` at an absolute ``file://`` URI.

    A relative source is looked up under each of ``search_dirs`` in turn (the dist dir, the
    build and source dirs of the markdown files, the document root). With ``crop_dir``, PNG/JPEG
    images are cropped of their uniform background margin into it first. Returns the HTML and
    the sources that were not found.
    """
    from paradoc.io.pdf.exporter import trim_whitespace

    missing: list[str] = []

    def replace(m: re.Match) -> str:
        src = html.unescape(m.group(2))
        if re.match(r"^[a-z][a-z0-9+.-]*:", src, re.IGNORECASE) or src.startswith("#"):
            return m.group(0)
        rel = urllib.parse.unquote(src.split("#", 1)[0].split("?", 1)[0])
        path = pathlib.Path(rel)
        if not path.is_absolute():
            path = next(((d / rel).resolve() for d in search_dirs if (d / rel).is_file()), None)
        if path is None or not path.is_file():
            missing.append(src)
            return m.group(0)
        if crop_dir is not None and path.suffix.lower() in _TRIMMABLE:
            crop_dir.mkdir(parents=True, exist_ok=True)
            stat = path.stat()
            digest = hashlib.sha1(f"{path}|{stat.st_mtime_ns}|{stat.st_size}".encode()).hexdigest()[:16]
            cropped = crop_dir / f"{digest}{path.suffix.lower()}"
            if cropped.is_file() or trim_whitespace(path, cropped, trim_padding):
                path = cropped
        return f"{m.group(1)}{html.escape(path.as_uri())}{m.group(3)}"

    return _IMG_SRC_RE.sub(replace, body), missing


_TABLE_RE = re.compile(r"<table\b([^>]*)>(.*?)</table>", re.S)
_CELL_RE = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.S)


def layout_tables(body: str, mode: str, short_chars: int) -> str:
    """Apply ``table_col_widths`` to the HTML tables.

    pandoc gives a table with long cells fixed relative column widths (from the markdown's
    dashes), which in print leaves short columns ("LC 1") wrapping beside empty space.
    "relative" keeps them; "auto" drops them so the browser sizes every column to its content;
    "content" does that too, and sets tables holding long text across the full text width
    (``pd-wide``) so that text wraps evenly.
    """
    if mode == "relative":
        return body

    def replace(m: re.Match) -> str:
        attrs, inner = m.group(1), m.group(2)
        inner = re.sub(r"<colgroup>.*?</colgroup>", "", inner, flags=re.S)
        attrs = re.sub(r'\sstyle="[^"]*"', "", attrs)
        longest = max((len(_plain(c)) for c in _CELL_RE.findall(inner)), default=0)
        if mode == "content" and longest > short_chars:
            attrs += ' class="pd-wide"' if "class=" not in attrs else ""
        return f"<table{attrs}>{inner}</table>"

    return _TABLE_RE.sub(replace, body)


def data_uri(path: pathlib.Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or ("image/svg+xml" if path.suffix.lower() == ".svg" else "image/png")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _esc(s: str) -> str:
    return html.escape(s or "")


def title_page_html(doc: DocumentInfo, logo_uri: Optional[str], title_logo_uri: Optional[str]) -> str:
    brand = ""
    if title_logo_uri:
        brand = f'<img src="{title_logo_uri}" alt="">'
        if not doc.title_page_logo and doc.company:
            brand += f'<span class="pd-company">{_esc(doc.company)}</span>'
    elif doc.company:
        brand = f'<span class="pd-company">{_esc(doc.company)}</span>'

    rows = [
        ("Document no.", doc.document_number),
        ("Revision", doc.revision),
        ("Issue date", doc.resolved_issue_date()),
        ("Status", doc.status),
        ("Client", doc.client),
        ("Prepared by", doc.prepared_by),
    ]
    docdata = "".join(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in rows if v)

    history = doc.revision_history()
    revhist = ""
    if history:
        cols = [("Rev", "rev"), ("Date", "date"), ("Description", "description"), ("Status", "status")]
        cols += [
            (lbl, key)
            for lbl, key in (("Prep.", "prepared"), ("Chk.", "checked"), ("Appr.", "approved"))
            if any(getattr(r, key) for r in history)
        ]
        head = "".join(f"<th>{lbl}</th>" for lbl, _ in cols)
        body_rows = []
        for r in reversed(history):  # newest on top, as on a drawing's revision block
            cells = []
            for _, key in cols:
                val = getattr(r, key) or (doc.status.title() if key == "status" else "")
                cells.append(f"<td>{_esc(val)}</td>")
            cls = ' class="pd-current"' if r.rev == doc.revision else ""
            body_rows.append(f"<tr{cls}>{''.join(cells)}</tr>")
        revhist = (
            '<div class="pd-revhist-title">Revision history</div>'
            f'<table class="pd-revhist"><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'
        )

    parts = [
        '<section class="pd-title">',
        f'<div class="pd-title-brand">{brand}</div>' if brand else "",
        '<div class="pd-title-rule"></div>',
        f'<div class="pd-title-project">{_esc(doc.project)}</div>' if doc.project else "",
        f'<div class="pd-title-main">{_esc(doc.title)}</div>' if doc.title else "",
        f'<div class="pd-title-sub">{_esc(doc.subtitle)}</div>' if doc.subtitle else "",
        f'<div class="pd-stamp">{_esc(doc.status)}</div>' if doc.status else "",
        f'<table class="pd-docdata"><tbody>{docdata}</tbody></table>' if docdata else "",
        f'<div class="pd-note">{_esc(doc.note)}</div>' if doc.note else "",
        '<div class="pd-spacer"></div>',
        revhist,
        "</section>",
    ]
    return "\n".join(p for p in parts if p)


def toc_html(headings: list[Heading], depth: int, pages: Optional[dict[str, int]] = None) -> str:
    items = []
    for h in headings:
        if h.level > depth or not h.number:
            continue
        pg = str(pages.get(h.anchor, "")) if pages else "000"
        items.append(
            f'<li class="l{h.level}"><a href="#{_esc(h.anchor)}"><span class="no">{_esc(h.number)}</span>'
            f'<span class="t">{_esc(h.text)}</span><span class="dots"></span>'
            f'<span class="pg">{pg}</span></a></li>'
        )
    return f'<nav class="pd-toc"><div class="pd-toc-title">Contents</div><ol>{"".join(items)}</ol></nav>'


def _band_style(cfg: PdfExportConfig, edge: str) -> str:
    """Inline style of a header/footer band (Chromium renders the templates without the page's CSS)."""
    rule = (
        f"border-bottom:0.6pt solid {cfg.accent_color};padding-bottom:1.6mm;"
        if edge == "top"
        else "border-top:0.5pt solid #c9d1d9;padding-top:1.4mm;"
    )
    return (
        f"width:100%;margin:0 {cfg.margin_right} 0 {cfg.margin_left};font-family:{_esc(cfg.font_family)};"
        f"font-size:7.5pt;line-height:1.35;color:#3b4148;display:flex;align-items:center;{rule}"
        "-webkit-print-color-adjust:exact;"
    )


def _branding(doc: DocumentInfo, cfg: PdfExportConfig, logo_uri: Optional[str]) -> str:
    logo = f'<img src="{logo_uri}" style="height:7.5mm;width:auto;margin-right:2.2mm">' if logo_uri else ""
    company = (
        f'<span style="font-weight:700;font-size:9pt;color:{cfg.accent_color};letter-spacing:0.02em">'
        f"{_esc(doc.company)}</span>"
        if doc.company
        else ""
    )
    return f'<div style="flex:1;display:flex;align-items:center">{logo}{company}</div>'


def _page_no() -> str:
    return 'Page <span class="pageNumber"></span> of <span class="totalPages"></span>'


def _document_cells(doc: DocumentInfo, cfg: PdfExportConfig) -> tuple[str, str]:
    """Left: project over document title. Right: status, revision and issue date over the page number."""
    title = doc.title or doc.document_number
    left = (
        f'<div style="flex:1"><div style="font-weight:700;color:{cfg.accent_color}">{_esc(doc.project or title)}</div>'
        + (f"<div>{_esc(title)}</div>" if doc.project and title else "")
        + "</div>"
    )
    meta = " \u00b7 ".join(
        _esc(m) for m in (f"Rev {doc.revision}" if doc.revision else "", doc.resolved_issue_date()) if m
    )
    right = f'<div style="text-align:right"><div>{meta}</div><div>{_page_no()}</div></div>'
    return left, right


def _status_mark(doc: DocumentInfo) -> str:
    if not doc.status:
        return ""
    return (
        '<div style="text-align:right"><span style="border:0.8pt solid #b42318;color:#b42318;font-weight:700;'
        f'padding:0.3mm 1.6mm">{_esc(doc.status)}</span></div>'
    )


def header_template(doc: DocumentInfo, cfg: PdfExportConfig, logo_uri: Optional[str]) -> str:
    """The page header. ``branding = "footer"`` (default): project and document title left, revision,
    issue date and page number right. ``branding = "header"``: logo and company left, project in
    the centre, status and revision right."""
    if cfg.branding == "header":
        right = " \u2013 ".join(p for p in (doc.status, f"Rev {doc.revision}" if doc.revision else "") if p)
        return (
            f'<div style="{_band_style(cfg, "top")}">{_branding(doc, cfg, logo_uri)}'
            f'<div style="flex:1.4;text-align:center">{_esc(doc.project or doc.title)}</div>'
            f'<div style="flex:1;text-align:right;font-weight:700;color:{cfg.accent_color}">{_esc(right)}</div>'
            "</div>"
        )
    left, right = _document_cells(doc, cfg)
    return f'<div style="{_band_style(cfg, "top")}">{left}{right}</div>'


def footer_template(doc: DocumentInfo, cfg: PdfExportConfig, logo_uri: Optional[str] = None) -> str:
    """The page footer. ``branding = "footer"`` (default): logo and company left, the status mark
    (eg DRAFT) right. ``branding = "header"``: document number, title and issue date left, page
    number right."""
    if cfg.branding == "header":
        left = [doc.document_number or doc.title]
        if doc.document_number and doc.title:
            left.append(doc.title)
        date = doc.resolved_issue_date()
        if date:
            left.append(f"Issued {date}")
        left_txt = " \u00b7 ".join(_esc(p) for p in left if p)
        return (
            f'<div style="{_band_style(cfg, "bottom")}"><div style="flex:1">{left_txt}</div>'
            f'<div style="text-align:right">{_page_no()}</div></div>'
        )
    return f'<div style="{_band_style(cfg, "bottom")}">{_branding(doc, cfg, logo_uri)}{_status_mark(doc)}</div>'


def _mm(length: str) -> float:
    m = re.fullmatch(r"\s*([\d.]+)\s*(mm|cm|in|pt|px)?\s*", length)
    if not m:
        raise ValueError(f"cannot read the page length {length!r} (use mm, cm, in, pt or px)")
    v, unit = float(m.group(1)), m.group(2) or "px"
    return v * {"mm": 1, "cm": 10, "in": 25.4, "pt": 25.4 / 72, "px": 25.4 / 96}[unit]


#: Shrinks a table wider than the text block: smaller type first, then a zoom.
_FIT_TABLES_JS = """
(minPt) => {
  const avail = document.querySelector('.pd-body').clientWidth;
  const fitted = [];
  for (const t of document.querySelectorAll('.pd-body table')) {
    if (t.scrollWidth <= avail + 1) continue;
    let size = parseFloat(getComputedStyle(t).fontSize) * 0.75;  // px -> pt
    const before = t.scrollWidth;
    while (t.scrollWidth > avail + 1 && size > minPt) {
      size -= 0.5;
      t.style.fontSize = size + 'pt';
    }
    if (t.scrollWidth > avail + 1) t.style.zoom = (avail / t.scrollWidth).toFixed(3);
    fitted.push([t.id || '(table)', before, avail, size, t.style.zoom || '1']);
  }
  return fitted;
}
"""


class ChromiumPdfExporter:
    def __init__(self, one_doc, config: PdfExportConfig | None = None):
        self.one_doc = one_doc
        self.config = config or PdfExportConfig(engine="chromium")

    # -- assembly ---------------------------------------------------------------------------
    def _search_dirs(self, out_dir: pathlib.Path) -> list[pathlib.Path]:
        one = self.one_doc
        dirs = [out_dir]
        for md in [*one.md_files_main, *one.md_files_app]:
            for d in (md.build_file.parent, md.path.parent):
                if d not in dirs:
                    dirs.append(d)
        for d in (pathlib.Path(one.build_dir), pathlib.Path(one.source_dir), pathlib.Path(one.doc_root)):
            if d not in dirs:
                dirs.append(d)
        return dirs

    def _asset(self, rel: Optional[str]) -> Optional[pathlib.Path]:
        if not rel:
            return None
        p = pathlib.Path(rel)
        if not p.is_absolute():
            p = pathlib.Path(self.one_doc.doc_root) / p
        if not p.is_file():
            raise FileNotFoundError(f"[build.<profile>.pdf.document] image not found: {p}")
        return p

    def build_html(self, out_dir: pathlib.Path) -> tuple[str, list[Heading]]:
        from paradoc.io.html.exporter import HTMLExporter
        from paradoc.utils import copy_figures_to_dist

        one, cfg = self.one_doc, self.config
        copy_figures_to_dist(one, out_dir)
        body = HTMLExporter(one).render_body(extra_pandoc_args=("--mathml",))
        body, headings = number_headings(body, max_level=max(3, cfg.toc_depth))
        body = layout_tables(body, cfg.table_col_widths, cfg.table_short_cell_chars)
        crop = out_dir / "_pdf_images" if cfg.figure_trim_whitespace else None
        body, missing = resolve_images(body, self._search_dirs(out_dir), crop, cfg.figure_trim_padding)
        for src in missing:
            logger.warning(f"PDF export: image not found: {src}")
        self._missing_images = missing
        return body, headings

    def page_html(self, body: str, headings: list[Heading], pages: Optional[dict[str, int]] = None) -> str:
        cfg, doc = self.config, self.config.document
        paper, w_mm, h_mm = _PAPER.get(cfg.papersize.lower(), _PAPER["a4"])
        content_h = h_mm - _mm(cfg.margin_top) - _mm(cfg.margin_bottom)
        logo = self._asset(doc.logo)
        title_logo = self._asset(doc.title_page_logo) or logo
        css = PRINT_CSS.read_text(encoding="utf-8")
        extra_css = ""
        if cfg.stylesheet:
            extra_css = self._asset(cfg.stylesheet).read_text(encoding="utf-8")
        variables = {
            "--pd-paper": paper,
            "--pd-font": cfg.font_family,
            "--pd-fontsize": cfg.fontsize,
            "--pd-accent": cfg.accent_color,
            "--pd-fig-max-w": f"{cfg.figure_max_width * 100:.0f}%",
            "--pd-fig-max-h": f"{cfg.figure_max_height * content_h:.1f}mm",
            "--pd-table-font": _TABLE_FONT[cfg.table_font_size],
            "--pd-content-h": f"{content_h - 1:.1f}mm",
        }
        root = ":root{" + ";".join(f"{k}:{v}" for k, v in variables.items()) + "}"
        front = []
        if cfg.title_page:
            front.append(title_page_html(doc, logo and data_uri(logo), title_logo and data_uri(title_logo)))
        if cfg.toc:
            front.append(toc_html(headings, cfg.toc_depth, pages))
        title = doc.title or doc.project or self.one_doc.doc_root.name
        body_cls = "pd-chapter-breaks" if cfg.chapter_page_break else ""
        return (
            '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
            f"<title>{_esc(title)}</title>"
            f"<style>{root}\n{css}\n{extra_css}</style></head>"
            f'<body class="{body_cls}">{"".join(front)}<main class="pd-body">{body}</main></body></html>'
        )

    # -- printing ---------------------------------------------------------------------------
    def _print(self, browser, html_file: pathlib.Path, pdf_file: pathlib.Path) -> list:
        cfg, doc = self.config, self.config.document
        paper, w_mm, _ = _PAPER.get(cfg.papersize.lower(), _PAPER["a4"])
        logo = self._asset(doc.logo)
        content_w_px = (w_mm - _mm(cfg.margin_left) - _mm(cfg.margin_right)) * 96 / 25.4
        page = browser.new_page(viewport={"width": int(content_w_px), "height": 1100})
        try:
            page.emulate_media(media="print")
            page.goto(html_file.as_uri(), wait_until="load", timeout=180_000)
            fitted = page.evaluate(_FIT_TABLES_JS, 6.0)
            page.pdf(
                path=str(pdf_file),
                format=paper,
                print_background=True,
                display_header_footer=True,
                header_template=header_template(doc, cfg, logo and data_uri(logo)),
                footer_template=footer_template(doc, cfg, logo and data_uri(logo)),
                margin={
                    "top": cfg.margin_top,
                    "bottom": cfg.margin_bottom,
                    "left": cfg.margin_left,
                    "right": cfg.margin_right,
                },
                outline=True,
                tagged=True,
            )
        finally:
            page.close()
        return fitted

    @staticmethod
    def heading_pages(pdf_file: pathlib.Path, headings: list[Heading]) -> dict[str, int]:
        """Page number (1-based) of each heading, from the PDF outline Chromium wrote.

        The outline lists the headings in document order with their numbered text, so it is
        walked alongside ``headings`` and matched on that text.
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning("PDF export: pypdf is not installed, the table of contents has no page numbers")
            return {}

        reader = PdfReader(str(pdf_file))
        flat: list[tuple[str, int]] = []

        def walk(items):
            for it in items:
                if isinstance(it, list):
                    walk(it)
                else:
                    try:
                        flat.append((re.sub(r"\s+", "", it.title or ""), reader.get_destination_page_number(it) + 1))
                    except Exception:  # noqa: BLE001 -- a destination pypdf cannot resolve
                        continue

        walk(reader.outline)
        pages: dict[str, int] = {}
        i = 0
        for h in headings:
            key = re.sub(r"\s+", "", f"{h.number}{h.text}")
            for j in range(i, len(flat)):
                if flat[j][0] == key or flat[j][0].endswith(re.sub(r"\s+", "", h.text)):
                    pages[h.anchor] = flat[j][1]
                    i = j + 1
                    break
        return pages

    def export(self, dest_file: pathlib.Path) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as err:  # pragma: no cover - depends on the environment
            raise ImportError(
                'The "chromium" PDF engine needs Playwright: "pip install playwright" or '
                '"conda install -c conda-forge playwright-python", then "playwright install chromium".'
            ) from err

        cfg = self.config
        dest_file = pathlib.Path(dest_file)
        out_dir = dest_file.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        body, headings = self.build_html(out_dir)
        html_file = out_dir / f"{dest_file.stem}.print.html"

        with sync_playwright() as p:
            browser = launch_browser(p, cfg.browser)
            try:
                html_file.write_text(self.page_html(body, headings), encoding="utf-8")
                if not cfg.toc:
                    fitted = self._print(browser, html_file, dest_file)
                else:
                    with tempfile.TemporaryDirectory() as tmp:
                        first = pathlib.Path(tmp) / "pass1.pdf"
                        self._print(browser, html_file, first)
                        pages = self.heading_pages(first, headings)
                    html_file.write_text(self.page_html(body, headings, pages), encoding="utf-8")
                    fitted = self._print(browser, html_file, dest_file)
            finally:
                browser.close()

        for tid, before, avail, size, zoom in fitted:
            logger.info(f"PDF export: table {tid} {before}px > {avail}px wide: set at {size}pt, zoom {zoom}")
        if not cfg.keep_html:
            html_file.unlink(missing_ok=True)
        print(f'Successfully exported PDF to "{dest_file}"')
