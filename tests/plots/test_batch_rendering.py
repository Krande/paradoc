"""Test batch plot rendering using write_images."""

import pandas as pd

from paradoc import OneDoc
from paradoc.db import DbManager, dataframe_to_plot_data


def test_batch_plot_rendering(tmp_path):
    """Test that multiple plots are rendered using batch write_images."""

    source_dir = tmp_path / "test_doc"
    source_dir.mkdir()

    # Create main directory
    main_dir = source_dir / "00-main"
    main_dir.mkdir()

    # Create database and add multiple plots
    db_path = source_dir / "data.db"
    db_manager = DbManager(db_path)

    # Create 3 different plots
    for i in range(3):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [i + 1, i + 2, i + 3, i + 4, i + 5]})
        plot_data = dataframe_to_plot_data(
            df=df, key=f"test_plot_{i}", plot_type="line", caption=f"Test Plot {i}", x_column="x", y_columns=["y"]
        )
        db_manager.add_plot(plot_data)

    # Close database connection
    if db_manager.connection:
        db_manager.connection.close()

    # Create a markdown file that references all 3 plots
    md_content = """# Test Document

Here are three plots:

{{__test_plot_0__}}

{{__test_plot_1__}}{plt:width:1000}

{{__test_plot_2__}}{plt:height:400}
"""

    md_file = main_dir / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    # Create OneDoc instance and compile
    one = OneDoc(source_dir=source_dir)

    # Get AST to trigger variable substitution and batch rendering
    one.get_ast()

    # Close database connections
    if one.db_manager.connection:
        one.db_manager.connection.close()

    # Check that cache directory was created
    cache_dir = one.work_dir / ".paradoc_cache" / "rendered_plots"
    assert cache_dir.exists(), "Cache directory should be created"

    # Check that all 3 plots were rendered (with their specific dimensions)
    # test_plot_0: default 800x600
    # test_plot_1: 1000x600
    # test_plot_2: 800x400
    expected_cache_files = [
        "test_plot_0_800x600.png",
        "test_plot_0_800x600.timestamp",
        "test_plot_1_1000x600.png",
        "test_plot_1_1000x600.timestamp",
        "test_plot_2_800x400.png",
        "test_plot_2_800x400.timestamp",
    ]

    for cache_file in expected_cache_files:
        cache_path = cache_dir / cache_file
        assert cache_path.exists(), f"Expected cache file {cache_file} should exist"

    # Check that the markdown was substituted correctly
    built_md = (one.build_dir / "00-main" / "test.md").read_text(encoding="utf-8")
    assert "![Test Plot 0](images/test_plot_0.png)" in built_md
    assert "![Test Plot 1](images/test_plot_1.png)" in built_md
    assert "![Test Plot 2](images/test_plot_2.png)" in built_md

    print("OK Batch plot rendering test passed!")


def test_batch_rendering_with_cache(tmp_path):
    """Test that cached plots are not re-rendered."""

    source_dir = tmp_path / "test_doc"
    source_dir.mkdir()

    main_dir = source_dir / "00-main"
    main_dir.mkdir()

    # Create database and add a plot
    db_path = source_dir / "data.db"
    db_manager = DbManager(db_path)

    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 2, 3]})
    plot_data = dataframe_to_plot_data(
        df=df, key="cached_plot", plot_type="line", caption="Cached Plot", x_column="x", y_columns=["y"]
    )
    db_manager.add_plot(plot_data)

    # Close database connection
    if db_manager.connection:
        db_manager.connection.close()

    md_content = "# Test\n\n{{__cached_plot__}}"
    md_file = main_dir / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    # First compilation
    one = OneDoc(source_dir=source_dir)
    one.get_ast()

    cache_dir = one.work_dir / ".paradoc_cache" / "rendered_plots"
    cache_png = cache_dir / "cached_plot_800x600.png"

    # Get the modification time of the cache file
    first_mtime = cache_png.stat().st_mtime

    # Close first instance's connection
    if one.db_manager.connection:
        one.db_manager.connection.close()

    # Second compilation (should use cache)
    one2 = OneDoc(source_dir=source_dir)
    one2.get_ast()

    # The cache file should not have been modified
    second_mtime = cache_png.stat().st_mtime

    # Close second instance's connection
    if one2.db_manager.connection:
        one2.db_manager.connection.close()

    assert first_mtime == second_mtime, "Cache file should not be re-rendered"

    print("OK Batch rendering with cache test passed!")


if __name__ == "__main__":
    test_batch_plot_rendering()
    test_batch_rendering_with_cache()
