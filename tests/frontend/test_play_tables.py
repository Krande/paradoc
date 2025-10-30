"""Test frontend rendering of interactive tables using Playwright."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data


@pytest.fixture
def doc_with_table(tmp_path):
    """Create a test document with a single interactive table."""
    test_dir = tmp_path / "test_table_frontend"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create markdown file FIRST before initializing OneDoc
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True, exist_ok=True)

    markdown_content = """# Test Document with Table

This document contains a single interactive table for testing purposes.

## Sample Data Table

{{__test_data_table__}}

The table above should show sample data with multiple columns.
"""

    md_file = main_dir / "test.md"
    md_file.write_text(markdown_content)

    # Create OneDoc instance AFTER the markdown file exists
    one = OneDoc(test_dir)

    # Create sample table data
    df = pd.DataFrame(
        {
            "Name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "Age": [25, 30, 35, 28, 42],
            "Score": [92.5, 87.3, 95.1, 88.7, 91.2],
            "City": ["New York", "London", "Paris", "Tokyo", "Berlin"],
        }
    )

    # Add table to database
    table_data = dataframe_to_table_data(key="test_data_table", df=df, caption="Sample Data Table")
    one.db_manager.add_table(table_data)

    return one


@pytest.fixture
def frontend_resources_dir():
    """Get the frontend resources directory path."""
    return Path(__file__).parent.parent.parent / "src" / "paradoc" / "frontend" / "resources"


def test_table_static_interactive_buttons_exist(
    doc_with_table, page, wait_for_frontend, frontend_resources_dir, ws_server
):
    """Test that Static and Interactive buttons are rendered for tables in the frontend."""
    from paradoc.frontend.frontend_handler import FrontendHandler

    # Capture console logs
    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_table, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_table.get_ast()

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Now send the document (frontend is already loaded in Playwright)
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for the document to be loaded and rendered
    page.wait_for_timeout(3000)

    # Debug: Print console logs
    print("\n=== CONSOLE LOGS ===")
    for log in console_logs:
        print(log)
    print("=== END CONSOLE LOGS ===\n")

    # Debug: Check docId via JavaScript
    doc_id = page.evaluate(
        "() => { const ctx = window; return ctx.__REACT_CONTEXT__ ? ctx.__REACT_CONTEXT__.docId : 'unknown'; }"
    )
    print(f"DocId from page context: {doc_id}")

    # Debug: Check if table data exists in IndexedDB
    table_exists = page.evaluate(
        """
        async () => {
            const dbName = 'paradoc-cache';
            const storeName = 'tables';
            
            return new Promise((resolve) => {
                const req = indexedDB.open(dbName, 3);
                req.onsuccess = () => {
                    const db = req.result;
                    const tx = db.transaction(storeName, 'readonly');
                    const store = tx.objectStore(storeName);
                    const getAllReq = store.getAllKeys();
                    getAllReq.onsuccess = () => {
                        const keys = getAllReq.result;
                        db.close();
                        resolve({ exists: true, keys: keys });
                    };
                    getAllReq.onerror = () => {
                        db.close();
                        resolve({ exists: false, error: 'Failed to get keys' });
                    };
                };
                req.onerror = () => resolve({ exists: false, error: 'Failed to open DB' });
            });
        }
    """
    )
    print(f"Table data in IndexedDB: {table_exists}")

    # Debug: Check if any tables exist at all
    all_tables = page.locator("table")
    print(f"Found {all_tables.count()} table elements")

    # Debug: Get table ID
    if all_tables.count() > 0:
        table_id = all_tables.first.get_attribute("id")
        print(f"Table ID: {table_id}")

    # Debug: Check for any divs with 'relative' class
    relative_divs = page.locator("div.relative")
    print(f"Found {relative_divs.count()} div.relative elements")

    # Debug: Check for div.relative.group
    interactive_divs = page.locator("div.relative.group")
    print(f"Found {interactive_divs.count()} div.relative.group elements")

    # Look for the table element with the interactive wrapper
    # The InteractiveTable component renders a div with class "relative group"
    table_container = page.locator("div.relative.group").first

    # Hover over the table to reveal the Static/Interactive buttons
    table_container.hover()

    # Wait for the button container to appear
    button_container = page.locator("div.absolute.top-2.right-2")
    button_container.wait_for(state="visible", timeout=5000)

    # Check that both Static and Interactive buttons exist
    static_button = page.locator('button:has-text("Static")')
    interactive_button = page.locator('button:has-text("Interactive")')

    assert static_button.count() > 0, "Static button not found"
    assert interactive_button.count() > 0, "Interactive button not found"

    # Verify the buttons have the cursor-pointer class (from style requirements)
    static_btn_classes = static_button.first.get_attribute("class")
    assert "cursor-pointer" in static_btn_classes, "Static button should have cursor-pointer class"

    interactive_btn_classes = interactive_button.first.get_attribute("class")
    assert "cursor-pointer" in interactive_btn_classes, "Interactive button should have cursor-pointer class"


def test_table_toggle_between_static_and_interactive(
    doc_with_table, page, wait_for_frontend, frontend_resources_dir, ws_server
):
    """Test switching between static and interactive table modes."""
    from paradoc.frontend.frontend_handler import FrontendHandler
    from paradoc.io.ast.exporter import ASTExporter

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_table, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_table.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # Hover to reveal buttons
    table_container = page.locator("div.relative.group").first
    table_container.hover()

    # Wait for buttons to appear
    page.wait_for_selector('button:has-text("Static")', timeout=5000)

    # Initially, Static should be selected (active)
    static_button = page.locator('button:has-text("Static")').first
    static_classes = static_button.get_attribute("class")
    assert "bg-blue-600" in static_classes, "Static button should be active initially"

    # Click Interactive button
    interactive_button = page.locator('button:has-text("Interactive")').first
    interactive_button.click()

    # Wait for the mode to change
    page.wait_for_timeout(500)

    # Now Interactive should be active
    interactive_classes = interactive_button.get_attribute("class")
    assert "bg-blue-600" in interactive_classes, "Interactive button should be active after clicking"

    # Static should no longer be active
    static_classes = static_button.get_attribute("class")
    assert "bg-blue-600" not in static_classes, "Static button should not be active after clicking Interactive"

    # Click back to Static
    static_button.click()
    page.wait_for_timeout(500)

    # Verify Static is active again
    static_classes = static_button.get_attribute("class")
    assert "bg-blue-600" in static_classes, "Static button should be active after clicking back"


def test_table_interactive_mode_renders_table(
    doc_with_table, page, wait_for_frontend, frontend_resources_dir, ws_server
):
    """Test that Interactive mode loads and renders an interactive table with sorting/filtering."""
    from paradoc.frontend.frontend_handler import FrontendHandler

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_table, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_table.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # Hover to reveal buttons
    table_container = page.locator("div.relative.group").first
    table_container.hover()

    # Click Interactive button
    interactive_button = page.locator('button:has-text("Interactive")').first
    interactive_button.click()

    # Wait for table to load and render
    page.wait_for_timeout(2000)

    # Look for the interactive table elements
    # The TableRenderer should render a table with interactive features
    interactive_table = page.locator("table").first

    # Check if table rendered
    assert interactive_table.is_visible(), "Interactive table should be visible in Interactive mode"

    # Verify table headers exist (columns: Name, Age, Score, City)
    headers = page.locator("th")
    assert headers.count() >= 4, "Table should have at least 4 column headers"

    # Verify per-column filter inputs exist (one for each column)
    filter_inputs = page.locator('input[placeholder*="Filter"]')
    assert filter_inputs.count() >= 4, f"Should have filter inputs for each column, found {filter_inputs.count()}"


def test_table_interactive_filtering(doc_with_table, page, wait_for_frontend, frontend_resources_dir, ws_server):
    """Test that the filter functionality works in interactive table mode."""
    from paradoc.frontend.frontend_handler import FrontendHandler

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_table, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_table.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # Switch to interactive mode
    table_container = page.locator("div.relative.group").first
    table_container.hover()
    interactive_button = page.locator('button:has-text("Interactive")').first
    interactive_button.click()
    page.wait_for_timeout(2000)

    # Count initial rows (should be 5 data rows)
    initial_rows = page.locator("tbody tr").count()
    assert initial_rows == 5, f"Should have 5 data rows initially, found {initial_rows}"

    # Type in the Name column filter input to filter for "Alice"
    name_filter_input = page.locator('input[placeholder*="Filter Name"]').first
    name_filter_input.fill("Alice")
    page.wait_for_timeout(500)

    # Count rows after filtering (should be 1 row)
    filtered_rows = page.locator("tbody tr").count()
    assert filtered_rows == 1, f"Should have 1 row after filtering for 'Alice', found {filtered_rows}"

    # Clear filter and check all rows are back
    name_filter_input.fill("")
    page.wait_for_timeout(500)
    rows_after_clear = page.locator("tbody tr").count()
    assert rows_after_clear == 5, f"Should have 5 rows after clearing filter, found {rows_after_clear}"


def test_table_interactive_sorting(doc_with_table, page, wait_for_frontend, frontend_resources_dir, ws_server):
    """Test that column sorting works in interactive table mode."""
    from paradoc.frontend.frontend_handler import FrontendHandler

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_table, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_table.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # Switch to interactive mode
    table_container = page.locator("div.relative.group").first
    table_container.hover()
    interactive_button = page.locator('button:has-text("Interactive")').first
    interactive_button.click()
    page.wait_for_timeout(2000)

    # Get all Name column values before sorting
    # Find the Name column index by looking at headers
    all_headers = page.locator("thead th")
    name_col_index = None
    for i in range(all_headers.count()):
        header_text = all_headers.nth(i).inner_text()
        if "Name" in header_text:
            name_col_index = i + 1  # CSS nth-child is 1-based
            break

    assert name_col_index is not None, "Could not find Name column header"

    # Get Name column cells using the correct index
    name_column_cells = page.locator(f"tbody tr td:nth-child({name_col_index})")

    # Click on the "Name" column header to sort (click the sortable div within the header)
    name_header = page.locator('th:has-text("Name") div.cursor-pointer').first
    name_header.click()
    page.wait_for_timeout(500)

    # Get the first row's Name value after sorting (should be Alice in ascending order)
    first_name_after = name_column_cells.first.inner_text()
    assert first_name_after == "Alice", f"After ascending sort, expected 'Alice' but got '{first_name_after}'"

    # Click again to reverse sort
    name_header.click()
    page.wait_for_timeout(500)

    # After reverse sort (descending), Eve should be first
    first_name_reversed = name_column_cells.first.inner_text()
    assert first_name_reversed == "Eve", f"After descending sort, expected 'Eve' but got '{first_name_reversed}'"


def test_table_static_mode_shows_html_table(doc_with_table, page, wait_for_frontend, frontend_resources_dir, ws_server):
    """Test that Static mode shows a static HTML table."""
    from paradoc.frontend.frontend_handler import FrontendHandler
    from paradoc.io.ast.exporter import ASTExporter

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_table, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_table.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # In static mode (default), we should see a table element
    table_element = page.locator("table").first

    # Check if table exists and is visible
    assert table_element.is_visible(), "Table should be visible in Static mode"

    # Verify that the filter input does NOT exist (it's only in interactive mode)
    filter_input = page.locator('input[placeholder*="Filter"]')
    # In static mode, filter should not be visible
    assert filter_input.count() == 0, "Filter input should not exist in static mode"


def test_table_caption_displayed(doc_with_table, page, wait_for_frontend, frontend_resources_dir, ws_server):
    """Test that table caption is displayed in both static and interactive modes."""
    from paradoc.frontend.frontend_handler import FrontendHandler

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_table, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_table.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # Check caption in static mode (look for caption text on page)
    caption_text = page.locator('text="Sample Data Table"')
    assert caption_text.count() > 0, "Caption should be visible in static mode"

    # Switch to interactive mode
    table_container = page.locator("div.relative.group").first
    table_container.hover()
    interactive_button = page.locator('button:has-text("Interactive")').first
    interactive_button.click()
    page.wait_for_timeout(2000)

    # Check caption still visible in interactive mode
    caption_text_interactive = page.locator('text="Sample Data Table"')
    assert caption_text_interactive.count() > 0, "Caption should be visible in interactive mode"
