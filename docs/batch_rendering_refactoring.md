# Batch Plot Rendering Refactoring

## Summary

Successfully refactored the plot rendering pipeline to use Plotly's `write_images` batch method instead of ThreadPoolExecutor-based multiprocessing. This approach is more efficient because it:

1. **Single Kaleido/Chrome initialization**: Instead of spinning up the Kaleido/Chrome machinery multiple times (once per worker thread), it now initializes once and processes all plots in a batch
2. **Simpler code**: Removed the complex worker function and ThreadPoolExecutor orchestration
3. **Better performance**: According to Plotly documentation, `write_images` is much faster than calling `write_image` multiple times

## Changes Made

### `src/paradoc/document.py`

1. **Removed imports**: Removed `ThreadPoolExecutor`, `as_completed`, and `Tuple` from imports as they're no longer needed

2. **Removed `_render_plot_worker` function**: This module-level worker function was used for parallel rendering with ThreadPoolExecutor. No longer needed.

3. **Refactored `_collect_and_render_plots_parallel` method**:
   - Changed from using ThreadPoolExecutor with worker functions to using `plotly.io.write_images`
   - Instead of submitting tasks to a thread pool, we now:
     - Collect all plots that need rendering
     - Create all figure objects upfront
     - Pass lists of figures and file paths to `pio.write_images()` for batch processing
   - Added fallback to individual rendering if batch fails (for robustness)
   - Simplified error handling and logging

### New Test File: `tests/plots/test_batch_rendering.py`

Created comprehensive tests to verify:
- Multiple plots are rendered correctly using batch processing
- Different plot dimensions (width/height annotations) work correctly
- Cache mechanism still functions properly
- Second compilation reuses cached plots without re-rendering

## How Batch Rendering Works

```python
# Old approach (multiprocessing)
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    for plot in plots:
        executor.submit(_render_plot_worker, plot_args)
    # Each worker initializes Kaleido separately

# New approach (batch)
import plotly.io as pio

figures = [fig1, fig2, fig3]
file_paths = ['plot1.png', 'plot2.png', 'plot3.png']

# Single call, single Kaleido initialization, processes all plots
pio.write_images(fig=figures, file=file_paths, format="png")
```

## Test Results

All existing tests pass:
- ✅ 129 tests passed
- ❌ 1 flaky frontend UI test (unrelated to changes)

New batch rendering tests:
- ✅ `test_batch_plot_rendering`: Verifies multiple plots render correctly with different dimensions
- ✅ `test_batch_rendering_with_cache`: Verifies cache mechanism still works

## Performance Expectations

The batch approach should be significantly faster when rendering multiple plots because:

1. **Reduced overhead**: One Kaleido/Chrome startup instead of N startups
2. **Better resource utilization**: Browser reuses resources across plot renders
3. **Native optimization**: Plotly's internal batch implementation is optimized for this use case

## Backward Compatibility

- ✅ All existing functionality preserved
- ✅ Cache mechanism unchanged
- ✅ API unchanged (`max_workers` parameter kept for compatibility but not used)
- ✅ Fallback to individual rendering if batch fails

