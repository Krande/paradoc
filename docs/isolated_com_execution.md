# Word COM API Isolated Process Execution

## Overview

The Word COM API wrapper now supports running in an isolated process to suppress C stack error logs that can clutter your test output. This is achieved by adding a `run_isolated=True` parameter to the `WordApplication` constructor.

## Usage

### Simple Usage

```python
from paradoc.io.word.com_api import WordApplication

# Add run_isolated=True to suppress C stack error logs
with WordApplication(visible=False, run_isolated=True) as word_app:
    doc = word_app.create_document()
    doc.add_heading("My Document", level=1)
    doc.add_paragraph("Content goes here.")
    doc.save("output.docx")
```

### How It Works

When `run_isolated=True`:
1. All document operations (add_heading, add_paragraph, etc.) are recorded
2. When `save()` is called, all operations are executed in an isolated subprocess
3. The subprocess runs with Windows error suppression enabled
4. C stack errors and other noise are contained within the subprocess
5. The document is saved and the subprocess terminates cleanly

### Benefits

- **Cleaner logs**: No more C stack trace errors in your test output
- **Same API**: No code changes needed except adding `run_isolated=True`
- **Transparent**: Operations are recorded and replayed automatically
- **Stable**: Each operation runs in a fresh process environment

### Performance Considerations

- Slightly slower than non-isolated mode due to process spawning
- Best for: Tests, automated document generation, production scripts
- Not recommended for: Interactive document editing, rapid iterations

### Example Test

```python
@pytest.mark.skipif(platform.system() != "Windows", reason="COM automation only available on Windows")
def test_create_document(tmp_path):
    """Create a document without C stack error logs."""
    output_file = tmp_path / "test.docx"

    with WordApplication(visible=False, run_isolated=True) as word_app:
        doc = word_app.create_document()
        
        # All operations work the same
        doc.add_heading("Section 1", level=1)
        fig_ref = doc.add_figure_with_caption("My figure", width=150, height=100)
        doc.add_text("See ")
        doc.add_cross_reference(fig_ref)
        
        # Save triggers execution in isolated process
        doc.save(str(output_file))
    
    assert output_file.exists()
```

### Backward Compatibility

The `run_isolated` parameter is optional and defaults to `False`. Existing code continues to work without changes:

```python
# Old code still works
with WordApplication(visible=False) as word_app:
    doc = word_app.create_document()
    doc.add_heading("Test")
    doc.save("output.docx")
```

## Alternative: Low-Level Isolated Execution

For more complex scenarios where you need to wrap custom functions, you can use the `run_word_operation_isolated` function:

```python
from paradoc.io.word.com_api import run_word_operation_isolated

def create_complex_document(output_path, data):
    from paradoc.io.word.com_api import WordApplication
    with WordApplication(visible=False) as word_app:
        doc = word_app.create_document()
        # ... complex operations ...
        doc.save(output_path)
    return output_path

# Run in isolated process
success, result, message = run_word_operation_isolated(
    create_complex_document,
    "output.docx",
    {"key": "value"},
    timeout_s=120.0
)

if not success:
    print(f"Failed: {message}")
```

## Implementation Details

- Uses Python's `multiprocessing` with `spawn` context for clean separation
- Operations are serialized and deserialized using dataclasses
- CaptionReference objects are preserved across process boundaries
- All Word COM interactions happen only in the isolated subprocess
- Windows error suppression is applied via `SetErrorMode` kernel32 API

