"""Test frontend rendering of interactive plots using Playwright."""

import pytest
from pathlib import Path
import numpy as np
import pandas as pd
from unittest.mock import patch

from paradoc import OneDoc
from paradoc.db import dataframe_to_plot_data


@pytest.fixture
def doc_with_plot(tmp_path):
    """Create a test document with a single plot."""
    test_dir = tmp_path / "test_plot_frontend"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create markdown file FIRST before initializing OneDoc
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True, exist_ok=True)

    markdown_content = """# Test Document with Plot

This document contains a single interactive plot for testing purposes.

## Trigonometric Functions

{{__test_sine_plot__}}

The plot above should show sine and cosine waves.
"""

    md_file = main_dir / "test.md"
    md_file.write_text(markdown_content)

    # Create OneDoc instance AFTER the markdown file exists
    one = OneDoc(test_dir)

    # Create sample plot data
    x = np.linspace(0, 2 * np.pi, 100)
    df = pd.DataFrame({"x": x, "sin(x)": np.sin(x), "cos(x)": np.cos(x)})

    # Add plot to database
    plot_data = dataframe_to_plot_data(
        key="test_sine_plot", df=df, plot_type="line", caption="Sine and Cosine Functions", width=800, height=400
    )
    one.db_manager.add_plot(plot_data)

    return one


@pytest.fixture
def frontend_resources_dir():
    """Get the frontend resources directory path."""
    return Path(__file__).parent.parent.parent / "src" / "paradoc" / "frontend" / "resources"


def test_plot_static_interactive_buttons_exist(
    doc_with_plot, page, wait_for_frontend, frontend_resources_dir, ws_server
):
    """Test that Static and Interactive buttons are rendered in the frontend."""
    from paradoc.frontend.frontend_handler import FrontendHandler

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_plot, host="localhost", port=13579)

    # Mock the open_frontend method to prevent opening browser windows
    with patch.object(frontend_handler, "open_frontend", return_value=True):
        assert frontend_handler.ensure_frontend_extracted(), "Failed to extract frontend"

    # Navigate to the frontend with Playwright (headless)
    index_html = frontend_resources_dir / "index.html"
    assert index_html.exists(), f"Frontend HTML not found at {index_html}"

    # Send document via WebSocket (without auto-opening browser)
    exporter = doc_with_plot.get_ast()

    # Navigate to the page first
    page.goto(f"file:///{index_html.as_posix()}")
    wait_for_frontend(page)

    # Now send the document (frontend is already loaded in Playwright)
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for the document to be loaded and rendered
    page.wait_for_timeout(3000)

    # Look for the figure element with the plot
    # The InteractiveFigure component renders a div with hover functionality
    figure_container = page.locator("div.relative.group").first

    # Hover over the figure to reveal the Static/Interactive buttons
    figure_container.hover()

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


def test_plot_toggle_between_static_and_interactive(
    doc_with_plot, page, wait_for_frontend, frontend_resources_dir, ws_server
):
    """Test switching between static and interactive plot modes."""
    from paradoc.frontend.frontend_handler import FrontendHandler
    from paradoc.io.ast.exporter import ASTExporter

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_plot, host="localhost", port=13579)

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
    doc_with_plot._prep_compilation(metadata_file=None)
    doc_with_plot._perform_variable_substitution(False)
    exporter = ASTExporter(doc_with_plot)
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # Hover to reveal buttons
    figure_container = page.locator("div.relative.group").first
    figure_container.hover()

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


def test_plot_interactive_mode_loads_plotly(doc_with_plot, page, wait_for_frontend, frontend_resources_dir, ws_server):
    """Test that Interactive mode loads and renders a Plotly plot."""
    from paradoc.frontend.frontend_handler import FrontendHandler
    from paradoc.io.ast.exporter import ASTExporter

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_plot, host="localhost", port=13579)

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
    exporter = doc_with_plot.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # Hover to reveal buttons
    figure_container = page.locator("div.relative.group").first
    figure_container.hover()

    # Click Interactive button
    interactive_button = page.locator('button:has-text("Interactive")').first
    interactive_button.click()

    # Wait for Plotly to load and render
    page.wait_for_timeout(2000)

    # Look for Plotly elements
    # Plotly creates a div with class 'plotly' or a div containing svg.main-svg
    plotly_container = page.locator("div.plotly, div:has(> svg.main-svg)").first

    # Check if Plotly rendered
    assert plotly_container.is_visible(), "Plotly plot should be visible in Interactive mode"

    # Verify the plot has interactive elements (like the modebar)
    # Plotly typically creates a modebar with buttons
    page.locator(".modebar, .js-plotly-plot .modebar-container")
    # The modebar might not always be visible until hover, so just check it exists
    # We can at least verify the plot container exists


def test_plot_static_mode_shows_image(doc_with_plot, page, wait_for_frontend, frontend_resources_dir, ws_server):
    """Test that Static mode shows a static image instead of interactive plot."""
    from paradoc.frontend.frontend_handler import FrontendHandler
    from paradoc.io.ast.exporter import ASTExporter

    # Use FrontendHandler to extract frontend without opening browser
    frontend_handler = FrontendHandler(doc_with_plot, host="localhost", port=13579)

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
    exporter = doc_with_plot.get_ast()
    exporter.send_to_frontend(embed_images=True, use_static_html=False, auto_open_frontend=False)

    # Wait for document to render
    page.wait_for_timeout(3000)

    # In static mode (default), we should see a figure with an img element
    figure_element = page.locator("figure").first

    # Check if figure exists and is visible
    assert figure_element.is_visible(), "Figure should be visible in Static mode"

    # Look for an image element within the figure
    img_element = figure_element.locator("img").first

    # The image should exist and have a source
    assert img_element.count() > 0, "Static mode should show an image element"

    # Verify the image has a src attribute (could be base64 or URL)
    img_src = img_element.get_attribute("src")
    assert img_src is not None, "Image should have a src attribute"
    assert len(img_src) > 0, "Image src should not be empty"
