# Cross-Reference Issues in Paradoc DOCX Export

## Root Cause - CONFIRMED

**Figure bookmarks ARE being created (`_Reffig_1-1`, `_Reffig_1-2`, etc.), but REF fields are NOT being created for figure cross-references.**

### Inspection Output Evidence:

**Working document:**
- 12 REF fields pointing to `_Ref212447685`, `_Ref212447687`, etc. (figures)
- 6 REF fields pointing to table bookmarks
- Total: 20 REF cross-references (for 6 figures + 6 tables, with 2 refs each - one for figure, one for table)

**Non-functional document:**
- 0 REF fields for figures ❌
- 6 REF fields pointing to `_Reftbl_1-1`, `_Reftbl_1-2`, etc. (tables only) ✓
- Total: 6 REF cross-references (only tables, NO figures)

### Why Tables Work But Figures Don't:

Looking at the markdown source:
```markdown
As shown in @fig:1-1 and @tbl:1-1, the data is consistent.
```

**After pandoc-crossref processes this:**
- `@fig:1-1` → `"Figure 1-1"` (plain text) ❌
- `@tbl:1-1` → `"Table 1-1"` (plain text that gets converted to REF field) ✓

**The problem:** The `convert_figure_references_to_ref_fields()` function is NOT finding or converting the figure references!

## What's Failing

In `src/paradoc/io/word/crossref.py`, the function `convert_figure_references_to_ref_fields()` is being called, but it's not creating any REF fields.

### Possible Reasons:

1. **Pattern mismatch**: The regex pattern doesn't match how pandoc-crossref formats figure references
2. **Bookmark extraction failing**: `_extract_bookmarks_from_figures()` returns empty list
3. **Caption detection failing**: The function can't find the paragraphs containing figure references

Need to add debug logging to see which part is failing.

