# Frontend Testing with Playwright

## Overview

This directory contains Playwright-based end-to-end tests for the Paradoc frontend. These tests verify that the React-based document reader correctly renders interactive elements and provides the expected user experience.

## Current Status

### ✅ Completed
- Created `tests/frontend/` directory structure
- Set up Playwright infrastructure in `conftest.py` with browser fixtures
- Created `test_play_figures.py` with comprehensive plot interaction tests
- Added playwright dependencies to `pyproject.toml` (test feature)
- Installed Playwright chromium browser

### ✅ Recently Fixed
- Removed the failing `assert result` statements since `send_to_frontend()` returns `None` with `use_static_html=True`
- Added `assert index_html.exists()` before navigation to verify frontend extraction
- Added autouse fixture in `conftest.py` that automatically installs Chromium if not found
- Cleaned up duplicate code and imports in test functions

## Test File: `test_play_figures.py`

### Purpose
Tests that interactive plots render correctly in the frontend with proper Static/Interactive toggle functionality.

### Test Cases

1. **`test_plot_static_interactive_buttons_exist`**
   - Creates a document with a single sine/cosine plot
   - Sends it to the static HTML frontend
   - Verifies that Static and Interactive buttons appear on hover
   - Checks that buttons have `cursor-pointer` class (per coding guidelines)

2. **`test_plot_toggle_between_static_and_interactive`**
   - Tests clicking between Static and Interactive modes
   - Verifies active state styling (`bg-blue-600` class)
   - Ensures proper toggle behavior

3. **`test_plot_interactive_mode_loads_plotly`**
   - Clicks the Interactive button
   - Verifies Plotly plot renders (looks for `.plotly` or `svg.main-svg`)
   - Confirms interactive plot elements are visible

4. **`test_plot_static_mode_shows_image`**
   - Verifies default Static mode shows an `<img>` element
   - Checks that image has a valid `src` attribute (base64 or URL)
### Fixtures

#### `ensure_playwright_installed` (autouse)
- Automatically checks if Chromium is installed before running tests
- If Chromium is not found, installs it automatically using `playwright install chromium`
- Runs once per test session, so no manual installation needed
- This fixture ensures tests can run immediately without manual setup

#### `doc_with_plot`
### Fixture: `doc_with_plot`
Creates a test document with:
- A markdown file in `00-main/test.md`
- A plot in the database (`test_sine_plot`)
- Sine and cosine data plotted as a line chart

## Next Steps

### Immediate Fixes Needed
1. **Fix the assertion issue**: Remove or adjust the `assert result` line in all tests since `send_to_frontend()` with `use_static_html=True` doesn't return a boolean
   ```python
   # Change this:
   result = doc_with_plot.send_to_frontend(embed_images=True, use_static_html=True)
   assert result, "Failed to send document to frontend"
   
   # To this:
   doc_with_plot.send_to_frontend(embed_images=True, use_static_html=True)
   # Or verify the frontend.zip was extracted instead
   ```

2. **Verify frontend extraction**: Add a check that `index.html` exists after `send_to_frontend()` completes

3. **Run tests**: Execute with `pixi run -e test pytest tests/frontend/test_play_figures.py -v`

### Future Enhancements
1. **Add more test files**:
   - `test_play_tables.py` - Test interactive table rendering
   - `test_play_equations.py` - Test equation rendering and cross-references
   - `test_play_navigation.py` - Test TOC navigation and section switching
   - `test_play_websocket.py` - Test WebSocket live updates

2. **Improve test robustness**:
   - Add better wait strategies (wait for specific elements vs. fixed timeouts)
   - Add screenshot capture on test failure
   - Add video recording for debugging
   - Consider headless vs. headed mode flag

3. **CI/CD Integration**:
   - Ensure Playwright browsers are cached in CI
   - Add GitHub Actions workflow for frontend tests
   - Consider running in parallel for faster execution

4. **Test utilities**:
   - Create helper functions for common operations (hover, click toggle, verify plot)
   - Add page object models for better maintainability

## Architecture

### How It Works
1. **Document Creation**: Test creates a temporary Paradoc document with plots/tables
2. **Frontend Extraction**: `send_to_frontend(use_static_html=True)` extracts `frontend.zip` to `src/paradoc/io/ast/resources/index.html`
3. **Browser Automation**: Playwright launches Chromium and navigates to the extracted HTML
4. **Element Verification**: Tests interact with and verify frontend React components

### Key Technologies
- **Playwright**: Browser automation (Chromium in headless mode)
- **React**: Frontend framework (TailwindCSS for styling)
- **Plotly.js**: Interactive plotting library
- **IndexedDB**: Browser storage for document data

### Frontend Components Tested
- `InteractiveFigure.tsx` - Provides Static/Interactive toggle for plots
- `PlotRenderer.tsx` - Renders interactive Plotly charts
- `VirtualReader.tsx` - Main document reader container

## Running Tests

```bash
# Run all frontend tests
pixi run -e test pytest tests/frontend/ -v

# Run specific test file
pixi run -e test pytest tests/frontend/test_play_figures.py -v

# Run single test with output
pixi run -e test pytest tests/frontend/test_play_figures.py::test_plot_static_interactive_buttons_exist -v -s

# Run with headed browser (for debugging)
pixi run -e test pytest tests/frontend/ -v --headed

# Generate HTML report
pixi run -e test pytest tests/frontend/ --html=report.html --self-contained-html
```

## Troubleshooting

### Playwright not installed
```bash
pixi install -e test
pixi run -e test playwright install chromium
```

### Tests timeout
- Increase timeout values in `wait_for_timeout()` calls
- Check if frontend is building correctly (`pixi run -e frontend wbuild`)
- Verify `index.html` exists in `src/paradoc/io/ast/resources/`

### Element not found
- Use `page.screenshot(path="debug.png")` to capture state
- Check browser console: `page.on("console", lambda msg: print(msg.text))`
- Verify React component structure hasn't changed

## References
- [Playwright Python Docs](https://playwright.dev/python/docs/intro)
- [pytest-playwright Plugin](https://github.com/microsoft/playwright-pytest)
- Paradoc Frontend: `frontend/src/components/InteractiveFigure.tsx`

