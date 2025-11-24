"""
CROSS-REFERENCE ISSUE ANALYSIS
================================

Updated: 2025-M10-24

## CRITICAL DISCOVERY: Missing SEQ Fields in Captions

After comparing XML structure between working COM API documents and Paradoc documents,
I've identified the root cause of cross-reference issues.

### The Problem (CONFIRMED):
**Paradoc documents have NO SEQ fields in figure/table captions.**

When Paradoc creates captions, they appear as static text:
```
Figure 1-1: Caption text
```

But Word requires dynamic SEQ (sequence) fields to properly number captions:
```
Figure <STYLEREF 1>-<SEQ Figure \* ARABIC \s 1>: Caption text
```

### Evidence from XML Comparison:

#### COM API Caption (WORKING) ✓:
```xml
<w:r><w:t>Figure </w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin" /></w:r>
<w:r><w:instrText> STYLEREF 1 \s \* MERGEFORMAT </w:instrText></w:r>
<w:r><w:fldChar w:fldCharType="separate" /></w:r>
<w:r><w:t>1</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end" /></w:r>
<w:r><w:t>-</w:t></w:r>
<w:r><w:fldChar w:fldCharType="begin" /></w:r>
<w:r><w:instrText> SEQ Figure \* ARABIC \s 1 \* MERGEFORMAT </w:instrText></w:r>
<w:r><w:fldChar w:fldCharType="separate" /></w:r>
<w:r><w:t>1</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end" /></w:r>
<w:r><w:t>: Caption text</w:t></w:r>
```

#### Paradoc Caption (BROKEN) ✗:
```xml
<w:r><w:t>Figure 1-1: Caption text</w:t></w:r>
```

### Test Results:
Running `test_xml_comparison.py`:
- **COM API document:** Found 2 SEQ fields ✓
- **Paradoc document:** Found 0 SEQ fields ✗

### Why This Breaks Cross-References:
1. Without SEQ fields, captions cannot auto-increment
2. All captions show "Figure 1-1" regardless of their actual position
3. When Word updates REF fields, they all resolve to "Figure 1-1"
4. Even though bookmarks are correctly placed, they point to identical text

### The Real Root Cause:
The issue is NOT with:
- Bookmark placement ✓ (bookmarks are correctly placed)
- REF field structure ✓ (REF fields have correct \h switch)
- Cross-reference conversion ✓ (pandoc-crossref [@fig:xxx] → REF fields works)

The issue IS with:
- **Caption numbering mechanism** ✗ (static text instead of SEQ fields)

### How Captions Are Currently Created:
Looking at the debug output from `test_comprehensive_crossref_with_figures_and_tables`:
```
[DEBUG _convert_references]   Caption #0: Figure 1-1 (text: Figure 1-1: Historical trends visualization)
[DEBUG _convert_references]   Caption #1: Figure 1-1 (text: Figure 1-1: Analysis results visualization)
[DEBUG _convert_references]   Caption #2: Figure 1-1 (text: Figure 1-1: Future projection visualization)
[DEBUG _convert_references]   WARNING: All captions show same number '1-1' - likely unevaluated SEQ fields
```

This confirms that captions are being inserted as static text "Figure 1-1" rather than
dynamic SEQ fields that Word can evaluate and update.

### The Fix Strategy:
We need to modify the caption creation process to insert proper Word field codes:

1. **For each figure/table caption:**
   - Insert "Figure " (or "Table ") as static text
   - Insert a STYLEREF field to get the chapter number
   - Insert "-" as static text
   - Insert a SEQ field with:
     - Identifier: "Figure" or "Table"
     - Format: \* ARABIC
     - Chapter separator: \s 1
     - Merge format: \* MERGEFORMAT
   - Insert ": caption text" as static text

2. **Place bookmarks around the entire label:**
   ```
   <bookmark start>
   Figure <STYLEREF><-><SEQ>
   <bookmark end>
   : caption text
   ```

### Where to Fix:
The caption creation likely happens in one of these locations:
- `src/paradoc/io/word/crossref_converter.py` - processes cross-references
- `src/paradoc/io/word/docx_composer.py` - composes the final document
- `src/paradoc/figures.py` - handles figure processing
- Pandoc template or filter that generates initial captions

### Latest Investigation (2025-01-24):

**Pandoc-crossref Output Format:**
Pandoc-crossref outputs references as: `"Figure1.1"` (no space, period separator)
NOT as: `"Figure 1-1"` (with space and hyphen)

**Fixed Regex Patterns:**
Updated crossref.py to match both formats:
- Changed pattern from `[\s\xa0]+([\d\-]+)` to `[\s\xa0]*([\d\.\-]+)`
- Now matches: "Figure1.1", "Figure1-1", "Figure 1", "Figure 1-1"

**New Issue Discovered:**
Debug logs show REF fields are being added correctly during processing:
```
[DEBUG _process_paragraph_references]   Added REF field #1: 2 -> index 1 -> _Reffig_analysis
[DEBUG _process_paragraph_references]   Added REF field #2: 1 -> index 0 -> _Reffig_trends
```

But when document is re-opened to verify, **only 1 REF field found** (out of 13 added).

**Root Cause Analysis:**
The REF fields are being created correctly in memory but are NOT persisting when the document is saved. This suggests:
1. The fields may not be properly attached to the paragraph element
2. Something is clearing them after they're added
3. The document save process might not be preserving the field structures

**Next Steps:**
1. ✓ Fixed regex patterns to match pandoc-crossref output
2. ✓ Confirmed SEQ fields ARE being created in captions
3. ✓ Confirmed bookmarks are correctly placed
4. ✓ Confirmed REF fields are linked to correct bookmarks
5. ⚠ INVESTIGATE: Why REF fields don't persist to saved document
6. Test if the issue is with create_ref_field_runs() function
7. Verify the paragraph element modification is working correctly

### Reference Documents:
- Working COM API document: `temp/test_compare_com_vs_paradoc_xm0/com_xml/`
- Broken Paradoc document: `temp/test_compare_com_vs_paradoc_xm0/paradoc_xml/`
- Comparison report: `temp/test_compare_com_vs_paradoc_xm0/crossref_comparison_report.md`
"""

if __name__ == "__main__":
    print(__doc__)

