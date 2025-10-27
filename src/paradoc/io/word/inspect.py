#!/usr/bin/env python
# coding: utf-8
"""
docx_inspector.py — minimal OOXML inspector for .docx
- Lists bookmarks
- Lists field codes (REF, PAGEREF, SEQ, etc.)
- Detects missing REF/PAGEREF targets and duplicate bookmark names

Usage:
    python docx_inspector.py /path/to/Main.docx
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
import pathlib
from dataclasses import dataclass
from xml.etree import ElementTree as ET
from typing import Sequence


# OOXML namespaces
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@dataclass(frozen=True)
class Bookmark:
    part: str
    id: str | None
    name: str | None
    context: str


@dataclass(frozen=True)
class Field:
    part: str
    kind: str  # "fldSimple" | "complex"
    instr: str
    context: str


@dataclass(frozen=True)
class CrossRef:
    field: Field
    ref_type: str  # "REF" | "PAGEREF" | "SEQ" | other
    target_or_label: str  # bookmark name for REF/PAGEREF; label for SEQ
    switches: tuple[str, ...]


class DocxInspector:
    def __init__(self, docx_path: str | pathlib.Path):
        self.path = pathlib.Path(docx_path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)

        # Load all word/*.xml parts (document, headers/footers, notes, etc.)
        self._parts: dict[str, ET.Element] = {}
        with zipfile.ZipFile(self.path) as zf:
            for name in zf.namelist():
                if not (name.startswith("word/") and name.endswith(".xml")):
                    continue
                try:
                    with zf.open(name) as f:
                        root = ET.fromstring(f.read())
                    self._parts[name] = root
                except ET.ParseError:
                    # Skip malformed or non-XML embedded content
                    continue

    # ---------------------- public API ----------------------

    def bookmarks(self) -> list[Bookmark]:
        out: list[Bookmark] = []
        for part, root in self._parts.items():
            for b in root.findall(".//w:bookmarkStart", NS):
                out.append(
                    Bookmark(
                        part=part,
                        id=b.get(f"{{{NS['w']}}}id"),
                        name=b.get(f"{{{NS['w']}}}name"),
                        context=self._context_for_element(root, b),
                    )
                )
        return out

    def fields(self) -> list[Field]:
        out: list[Field] = []
        for part, root in self._parts.items():
            # 1) Simple fields: <w:fldSimple w:instr="...">...</w:fldSimple>
            for fld in root.findall(".//w:fldSimple", NS):
                instr = fld.get(f"{{{NS['w']}}}instr") or ""
                out.append(
                    Field(
                        part=part,
                        kind="fldSimple",
                        instr=_squash_ws(instr),
                        context=self._context_for_element(root, fld),
                    )
                )

            # 2) Complex fields: <w:fldChar w:fldCharType="begin"/> ... <w:instrText>...</w:instrText> ... <w:fldChar w:fldCharType="end"/>
            for begin in root.findall(".//w:fldChar[@w:fldCharType='begin']", NS):
                instr = self._instr_text_for_complex_field(root, begin)
                if instr:
                    out.append(
                        Field(
                            part=part,
                            kind="complex",
                            instr=_squash_ws(instr),
                            context=self._context_for_element(root, begin),
                        )
                    )
        return out

    def cross_refs(self) -> list[CrossRef]:
        out: list[CrossRef] = []
        for f in self.fields():
            parsed = _parse_instr(f.instr)
            if parsed is None:
                continue
            out.append(
                CrossRef(
                    field=f,
                    ref_type=parsed.ref_type,
                    target_or_label=parsed.target_or_label,
                    switches=parsed.switches,
                )
            )
        return out

    def missing_ref_targets(self) -> list[CrossRef]:
        """REF/PAGEREF that point to a non-existent bookmark name."""
        bm_names = {b.name for b in self.bookmarks() if b.name}
        missing: list[CrossRef] = []
        for cr in self.cross_refs():
            if cr.ref_type in {"REF", "PAGEREF"}:
                target = cr.target_or_label
                if not target or target not in bm_names:
                    missing.append(cr)
        return missing

    def duplicate_bookmark_names(self) -> dict[str, list[Bookmark]]:
        """Bookmark names that appear more than once."""
        by_name: dict[str, list[Bookmark]] = {}
        for b in self.bookmarks():
            name = b.name or ""
            if not name:
                # Word often inserts a "_GoBack" or empty; include anyway
                pass
            by_name.setdefault(name, []).append(b)
        return {n: lst for n, lst in by_name.items() if n and len(lst) > 1}

    def seq_labels(self) -> set[str]:
        """All distinct SEQ labels seen (e.g., 'Figure', 'Table')."""
        labels: set[str] = set()
        for cr in self.cross_refs():
            if cr.ref_type == "SEQ" and cr.target_or_label:
                labels.add(cr.target_or_label)
        return labels

    def unused_bookmarks(self) -> list[Bookmark]:
        """Bookmarks that no REF/PAGEREF points to."""
        used_targets = {
            cr.target_or_label for cr in self.cross_refs() if cr.ref_type in {"REF", "PAGEREF"} and cr.target_or_label
        }
        return [b for b in self.bookmarks() if b.name and b.name not in used_targets]

    # ---------------------- internals ----------------------

    def _context_for_element(self, root: ET.Element, elem: ET.Element, max_len: int = 200) -> str:
        """Find nearest paragraph containing elem and return its visible text."""
        # xml.etree doesn't support parent pointers; scan paragraphs
        for p in root.findall(".//w:p", NS):
            if elem in list(p.iter()):
                return _visible_text_of(p)[:max_len]
        return ""

    def _instr_text_for_complex_field(self, root: ET.Element, begin: ET.Element) -> str:
        """
        Gather instrText between fldChar begin and the next 'separate' or 'end'
        within the same paragraph (common case for REF/SEQ fields).
        """
        # Find containing paragraph
        par: ET.Element | None = None
        for p in root.findall(".//w:p", NS):
            if begin in list(p.iter()):
                par = p
                break
        if par is None:
            return ""

        capture = False
        chunks: list[str] = []
        for el in par.iter():
            if el.tag == f"{{{NS['w']}}}fldChar":
                t = el.get(f"{{{NS['w']}}}fldCharType")
                if t == "begin":
                    capture = True
                    continue
                if capture and t in {"separate", "end"}:
                    break
            if capture and el.tag == f"{{{NS['w']}}}instrText":
                if el.text:
                    chunks.append(el.text)
        return " ".join(chunks).strip()


# ---------------------- helpers & parsing ----------------------


def _visible_text_of(elem: ET.Element) -> str:
    return "".join(t.text or "" for t in elem.findall(".//w:t", NS))


def _squash_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


@dataclass(frozen=True)
class ParsedInstr:
    ref_type: str  # REF | PAGEREF | SEQ | other
    target_or_label: str  # bookmark name (REF/PAGEREF) or label (SEQ)
    switches: tuple[str, ...]  # e.g. ("\h", "\p")


def _parse_instr(instr: str) -> ParsedInstr | None:
    """
    Parse common Word field instruction formats:
      - REF BookmarkName \h \p
      - PAGEREF BookmarkName \h
      - SEQ Figure \* ARABIC
    Returns None if it doesn't look like REF/PAGEREF/SEQ.
    """
    if not instr:
        return None
    tokens = _tokenize_instr(instr)
    if not tokens:
        return None

    head = tokens[0].upper()
    if head not in {"REF", "PAGEREF", "SEQ"}:
        return None

    # Find first non-switch argument after the head
    arg: str = ""
    switches: list[str] = []
    for tok in tokens[1:]:
        if tok.startswith("\\"):
            switches.append(tok)
        elif not arg:
            arg = tok

    # For REF/PAGEREF, arg = bookmark name; for SEQ, arg = sequence label
    return ParsedInstr(ref_type=head, target_or_label=arg, switches=tuple(switches))


def _tokenize_instr(instr: str) -> list[str]:
    """
    Tokenize instruction text. Handles simple quoted targets:
      REF "_Ref1234 5678" \h
    """
    s = instr.strip()
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        if s[i] in {'"', "'"}:
            quote = s[i]
            i += 1
            start = i
            while i < len(s) and s[i] != quote:
                i += 1
            out.append(s[start:i])
            i += 1  # skip closing quote
        else:
            start = i
            while i < len(s) and not s[i].isspace():
                i += 1
            out.append(s[start:i])
    return out


# ---------------------- CLI ----------------------


def _print_summary(di: DocxInspector) -> None:
    bms = di.bookmarks()
    flds = di.fields()
    xrs = di.cross_refs()

    print(f"[Bookmarks] count={len(bms)}")
    dup = di.duplicate_bookmark_names()
    if dup:
        print("  Duplicates:")
        for name, items in dup.items():
            parts = ", ".join(sorted({it.part for it in items}))
            print(f"   - {name!r}: {len(items)} occurrences (parts: {parts})")

    print(f"\n[Fields] count={len(flds)}")
    print(f"[Cross-Refs] count={len(xrs)}")
    print("  Types:", ", ".join(sorted({xr.ref_type for xr in xrs})) or "-")

    missing = di.missing_ref_targets()
    if missing:
        print("\n[Missing REF/PAGEREF targets]")
        for xr in missing:
            print(f"  - part={xr.field.part} | instr={xr.field.instr!r} | target={xr.target_or_label!r}")

    unused = di.unused_bookmarks()
    if unused:
        print("\n[Unused bookmarks] (not referenced by REF/PAGEREF)")
        for b in unused[:50]:  # cap output
            print(f"  - {b.name!r} in {b.part}  context={b.context[:80]!r}")
        if len(unused) > 50:
            print(f"  ... and {len(unused) - 50} more")

    labels = di.seq_labels()
    if labels:
        print("\n[SEQ labels] ->", ", ".join(sorted(labels)))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Inspect OOXML bookmarks and cross-references in a .docx")
    ap.add_argument("docx", type=pathlib.Path, help="Path to .docx file")
    args = ap.parse_args(argv)

    try:
        di = DocxInspector(args.docx)
        _print_summary(di)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return 0
