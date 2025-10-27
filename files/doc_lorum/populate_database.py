"""
Script to populate the doc_lorum database with all plots and tables using DbManager.

This script creates all the plot and table data for the doc_lorum example and stores
them in the database so they can be referenced with {{__key__}} syntax in markdown.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data, plotly_figure_to_plot_data


def create_plots(one: OneDoc):
    """Create and store all plot data in the database."""
    
    print("Creating plots...")
    
    # Plot 1: Historical trends
    years = np.arange(2015, 2025)
    trend = 50 + 5 * (years - 2015) + np.random.randn(10) * 3
    df1 = pd.DataFrame({"Year": years, "Performance Index": trend})
    fig1 = px.line(df1, x="Year", y="Performance Index", markers=True, title="Historical Trends Analysis")
    fig1.update_layout(template="plotly_white")
    
    plot1 = plotly_figure_to_plot_data(
        key="historical_trends",
        fig=fig1,
        caption="Historical trends visualization",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot1)
    print(f"  ✓ Added plot: {plot1.key}")
    
    # Plot 2: Data framework
    categories = ["Collection", "Processing", "Analysis", "Validation", "Storage"]
    values = [85, 92, 88, 95, 90]
    df2 = pd.DataFrame({"Category": categories, "Efficiency": values})
    fig2 = px.bar(df2, y="Category", x="Efficiency", orientation="h", title="Data Collection Framework Efficiency")
    fig2.update_layout(xaxis_range=[0, 100], template="plotly_white")
    
    plot2 = plotly_figure_to_plot_data(
        key="data_framework",
        fig=fig2,
        caption="Data collection framework architecture",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot2)
    print(f"  ✓ Added plot: {plot2.key}")
    
    # Plot 3: Statistical workflow
    steps = ["Raw Data", "Preprocessing", "Statistical\nTests", "Model\nFitting", "Validation", "Results"]
    completeness = [100, 98, 95, 92, 96, 94]
    df3 = pd.DataFrame({"Step": steps, "Completeness": completeness})
    fig3 = px.line(df3, x="Step", y="Completeness", markers=True, title="Statistical Analysis Workflow")
    fig3.update_layout(yaxis_range=[80, 105], template="plotly_white")
    
    plot3 = plotly_figure_to_plot_data(
        key="statistical_workflow",
        fig=fig3,
        caption="Statistical analysis workflow",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot3)
    print(f"  ✓ Added plot: {plot3.key}")
    
    # Plot 4: Primary results
    np.random.seed(42)
    x = np.linspace(0, 10, 100)
    y1 = 50 + 30 * np.sin(x) + np.random.randn(100) * 2
    y2 = 60 + 25 * np.cos(x) + np.random.randn(100) * 2
    df4 = pd.DataFrame(
        {
            "Parameter X": np.concatenate([x, x]),
            "Response": np.concatenate([y1, y2]),
            "Condition": ["Condition A"] * 100 + ["Condition B"] * 100,
        }
    )
    fig4 = px.scatter(df4, x="Parameter X", y="Response", color="Condition", title="Primary Experimental Results and Trends")
    fig4.update_layout(template="plotly_white")
    
    plot4 = plotly_figure_to_plot_data(
        key="primary_results",
        fig=fig4,
        caption="Primary experimental results and trends",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot4)
    print(f"  ✓ Added plot: {plot4.key}")
    
    # Plot 5: Comparative analysis
    conditions = ["Cond 1", "Cond 2", "Cond 3", "Cond 4", "Cond 5"]
    group_a = [88.5, 76.2, 91.7, 84.3, 79.8]
    group_b = [92.3, 79.8, 88.4, 86.9, 82.5]
    group_c = [85.7, 81.5, 93.2, 87.1, 80.3]
    df5 = pd.DataFrame(
        {
            "Condition": conditions * 3,
            "Score": group_a + group_b + group_c,
            "Group": ["Group A"] * 5 + ["Group B"] * 5 + ["Group C"] * 5,
        }
    )
    fig5 = px.bar(
        df5, x="Condition", y="Score", color="Group", barmode="group", title="Comparative Analysis Across Conditions"
    )
    fig5.update_layout(template="plotly_white")
    
    plot5 = plotly_figure_to_plot_data(
        key="comparative_analysis",
        fig=fig5,
        caption="Comparative analysis across experimental conditions",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot5)
    print(f"  ✓ Added plot: {plot5.key}")
    
    # Plot 6: Error analysis
    np.random.seed(123)
    errors = np.random.normal(0, 2, 1000)
    df6 = pd.DataFrame({"Error": errors})
    fig6 = px.histogram(df6, x="Error", nbins=40, title="Error Distribution and Uncertainty Analysis")
    fig6.update_layout(template="plotly_white")
    
    plot6 = plotly_figure_to_plot_data(
        key="error_analysis",
        fig=fig6,
        caption="Error distribution and uncertainty analysis",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot6)
    print(f"  ✓ Added plot: {plot6.key}")
    
    # Plot 7: Theory comparison
    x = np.linspace(0, 10, 100)
    theoretical = 50 + 20 * np.exp(-x / 5) * np.sin(2 * x)
    experimental = theoretical + np.random.randn(100) * 3
    df7 = pd.DataFrame({"Input Parameter": x, "Theoretical": theoretical, "Experimental": experimental})
    
    fig7 = go.Figure()
    fig7.add_trace(go.Scatter(x=df7["Input Parameter"], y=df7["Theoretical"], 
                              mode='lines', name='Theoretical', line=dict(color='blue', width=2)))
    fig7.add_trace(go.Scatter(x=df7["Input Parameter"], y=df7["Experimental"], 
                              mode='markers', name='Experimental', marker=dict(color='red', size=6)))
    fig7.update_layout(title="Comparison between theoretical predictions and experimental results",
                      xaxis_title="Input Parameter", yaxis_title="Response",
                      template="plotly_white")
    
    plot7 = plotly_figure_to_plot_data(
        key="theory_comparison",
        fig=fig7,
        caption="Comparison between theoretical predictions and experimental results",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot7)
    print(f"  ✓ Added plot: {plot7.key}")
    
    # Appendix plots
    # Plot 8: System architecture (placeholder)
    np.random.seed(456)
    df8 = pd.DataFrame({
        "Component": ["Frontend", "Backend", "Database", "Cache", "Queue"],
        "Load": np.random.randint(20, 95, 5)
    })
    fig8 = px.bar(df8, x="Component", y="Load", title="Detailed System Architecture Diagram")
    fig8.update_layout(template="plotly_white")
    
    plot8 = plotly_figure_to_plot_data(
        key="system_architecture",
        fig=fig8,
        caption="Detailed system architecture diagram",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot8)
    print(f"  ✓ Added plot: {plot8.key}")
    
    # Plot 9: Performance benchmarks
    configs = ["Config A", "Config B", "Config C", "Config D"]
    metrics = ["Throughput", "Latency", "CPU", "Memory"]
    data = []
    for config in configs:
        for metric in metrics:
            data.append({
                "Configuration": config,
                "Metric": metric,
                "Score": np.random.uniform(60, 95)
            })
    df9 = pd.DataFrame(data)
    fig9 = px.bar(df9, x="Configuration", y="Score", color="Metric", barmode="group",
                  title="Performance Benchmark Results Across Different Configurations")
    fig9.update_layout(template="plotly_white")
    
    plot9 = plotly_figure_to_plot_data(
        key="performance_benchmarks",
        fig=fig9,
        caption="Performance benchmark results across different configurations",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot9)
    print(f"  ✓ Added plot: {plot9.key}")
    
    # Plot 10: Time series
    dates = pd.date_range('2024-01-01', periods=100)
    values = 50 + np.cumsum(np.random.randn(100) * 2)
    df10 = pd.DataFrame({"Date": dates, "Value": values})
    fig10 = px.line(df10, x="Date", y="Value", title="Time Series Analysis of Key Parameters")
    fig10.update_layout(template="plotly_white")
    
    plot10 = plotly_figure_to_plot_data(
        key="time_series",
        fig=fig10,
        caption="Time series analysis of key parameters",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot10)
    print(f"  ✓ Added plot: {plot10.key}")
    
    # Plot 11: Computational results
    x = np.linspace(-5, 5, 50)
    y = np.linspace(-5, 5, 50)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.sqrt(X**2 + Y**2))
    fig11 = go.Figure(data=[go.Contour(z=Z, x=x, y=y, colorscale='Viridis')])
    fig11.update_layout(title="Computational Simulation Results", template="plotly_white")
    
    plot11 = plotly_figure_to_plot_data(
        key="computational_results",
        fig=fig11,
        caption="Computational simulation results",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot11)
    print(f"  ✓ Added plot: {plot11.key}")
    
    # Plot 12: Correlation matrix
    np.random.seed(789)
    vars = ["Var A", "Var B", "Var C", "Var D", "Var E"]
    corr_matrix = np.random.uniform(-1, 1, (5, 5))
    corr_matrix = (corr_matrix + corr_matrix.T) / 2  # Make symmetric
    np.fill_diagonal(corr_matrix, 1)
    fig12 = go.Figure(data=go.Heatmap(z=corr_matrix, x=vars, y=vars, colorscale='RdBu', zmid=0))
    fig12.update_layout(title="Correlation Matrix Heatmap", template="plotly_white")
    
    plot12 = plotly_figure_to_plot_data(
        key="correlation_matrix",
        fig=fig12,
        caption="Correlation matrix heatmap",
        width=700,
        height=600
    )
    one.db_manager.add_plot(plot12)
    print(f"  ✓ Added plot: {plot12.key}")
    
    # Plot 13: Distributions
    np.random.seed(101)
    fig13 = go.Figure()
    for i, name in enumerate(['Param A', 'Param B', 'Param C']):
        data = np.random.normal(loc=i*10, scale=5, size=200)
        fig13.add_trace(go.Histogram(x=data, name=name, opacity=0.7))
    fig13.update_layout(title="Distribution Plots for All Parameters", barmode='overlay', template="plotly_white")
    
    plot13 = plotly_figure_to_plot_data(
        key="distributions",
        fig=fig13,
        caption="Distribution plots for all parameters",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot13)
    print(f"  ✓ Added plot: {plot13.key}")
    
    # Plot 14: 3D surface
    x = np.linspace(-5, 5, 30)
    y = np.linspace(-5, 5, 30)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.sqrt(X**2 + Y**2)) * np.exp(-0.1 * np.sqrt(X**2 + Y**2))
    fig14 = go.Figure(data=[go.Surface(z=Z, x=x, y=y, colorscale='Viridis')])
    fig14.update_layout(title="3D Surface Plot of Interaction Effects", template="plotly_white")
    
    plot14 = plotly_figure_to_plot_data(
        key="surface_plot",
        fig=fig14,
        caption="3D surface plot of interaction effects",
        width=800,
        height=600
    )
    one.db_manager.add_plot(plot14)
    print(f"  ✓ Added plot: {plot14.key}")
    
    # Plot 15: Box plots
    np.random.seed(202)
    data = []
    for condition in ['Condition A', 'Condition B', 'Condition C', 'Condition D']:
        for group in ['Group 1', 'Group 2', 'Group 3']:
            values = np.random.normal(loc=70, scale=15, size=30)
            for val in values:
                data.append({'Condition': condition, 'Group': group, 'Value': val})
    df15 = pd.DataFrame(data)
    fig15 = px.box(df15, x="Condition", y="Value", color="Group", title="Statistical Distributions by Condition and Group")
    fig15.update_layout(template="plotly_white")
    
    plot15 = plotly_figure_to_plot_data(
        key="box_plots",
        fig=fig15,
        caption="Statistical distributions by condition and group",
        width=800,
        height=500
    )
    one.db_manager.add_plot(plot15)
    print(f"  ✓ Added plot: {plot15.key}")


def create_tables(one: OneDoc):
    """Create and store all table data in the database."""
    
    print("\nCreating tables...")
    
    # Table 1: Current metrics
    df1 = pd.DataFrame({
        "Metric Name": ["Performance Index", "Efficiency Rating", "Reliability Score", "Cost Effectiveness", "User Satisfaction"],
        "Value": [94.5, 87.2, 91.8, 78.5, 89.3],
        "Unit": ["%", "%", "%", "%", "%"],
        "Status": ["Excellent", "Good", "Excellent", "Good", "Excellent"]
    })
    table1 = dataframe_to_table_data(
        key="current_metrics",
        df=df1,
        caption="Current performance metrics summary",
        show_index=False
    )
    one.db_manager.add_table(table1)
    print(f"  ✓ Added table: {table1.key}")
    
    # Table 2: Measurement specs
    df2 = pd.DataFrame({
        "Parameter": ["Temperature", "Pressure", "Flow Rate", "Viscosity", "pH Level"],
        "Range": ["20-80 °C", "0-100 bar", "0-500 L/h", "1-100 cP", "0-14"],
        "Precision": ["±0.5 °C", "±0.1 bar", "±2 L/h", "±0.5 cP", "±0.05"],
        "Frequency": ["1 Hz", "10 Hz", "1 Hz", "0.1 Hz", "0.5 Hz"],
        "Method": ["Digital", "Analog", "Digital", "Manual", "Digital"]
    })
    table2 = dataframe_to_table_data(
        key="measurement_specs",
        df=df2,
        caption="Measurement specifications and protocols",
        show_index=False
    )
    one.db_manager.add_table(table2)
    print(f"  ✓ Added table: {table2.key}")
    
    # Table 3: Validation results
    df3 = pd.DataFrame({
        "Test Case": ["Baseline Test A", "Stress Test B", "Edge Case C", "Integration Test", "Performance Test"],
        "Expected": [100.0, 85.0, 75.0, 90.0, 95.0],
        "Observed": [99.8, 86.3, 74.1, 91.5, 93.8],
        "Variance": ["-0.2%", "+1.5%", "-1.2%", "+1.7%", "-1.3%"],
        "Pass/Fail": ["Pass", "Pass", "Pass", "Pass", "Pass"]
    })
    table3 = dataframe_to_table_data(
        key="validation_results",
        df=df3,
        caption="Validation test results summary",
        show_index=False
    )
    one.db_manager.add_table(table3)
    print(f"  ✓ Added table: {table3.key}")
    
    # Table 4: Quantitative metrics
    df4 = pd.DataFrame({
        "Category": ["Performance Score", "Efficiency Index", "Quality Rating", "Cost Factor", "Time Efficiency"],
        "Minimum": [72.3, 65.8, 78.2, 45.6, 68.4],
        "Maximum": [98.7, 95.4, 99.1, 88.9, 96.3],
        "Mean": [87.5, 82.3, 90.2, 70.5, 84.7],
        "Std Dev": [6.2, 7.8, 5.1, 10.3, 6.9],
        "Median": [88.1, 83.2, 91.0, 71.2, 85.5]
    })
    table4 = dataframe_to_table_data(
        key="quantitative_metrics",
        df=df4,
        caption="Quantitative analysis metrics",
        show_index=False
    )
    one.db_manager.add_table(table4)
    print(f"  ✓ Added table: {table4.key}")
    
    # Table 5: Comparison data
    df5 = pd.DataFrame({
        "Condition": ["Scenario 1", "Scenario 2", "Scenario 3", "Scenario 4", "Scenario 5"],
        "Group A": [88.5, 76.2, 91.7, 84.3, 79.8],
        "Group B": [92.3, 79.8, 88.4, 86.9, 82.5],
        "Group C": [85.7, 81.5, 93.2, 87.1, 80.3],
        "Delta A-B": ["+3.8", "+3.6", "-3.3", "+2.6", "+2.7"],
        "Delta B-C": ["+6.6", "-1.7", "-4.8", "-0.2", "+2.2"]
    })
    table5 = dataframe_to_table_data(
        key="comparison_data",
        df=df5,
        caption="Comparative analysis data across scenarios",
        show_index=False
    )
    one.db_manager.add_table(table5)
    print(f"  ✓ Added table: {table5.key}")
    
    # Table 6: Implementation guide
    df6 = pd.DataFrame({
        "Phase": ["Planning", "Development", "Testing", "Deployment", "Monitoring"],
        "Duration": ["2 weeks", "8 weeks", "4 weeks", "3 weeks", "Ongoing"],
        "Resources": ["5 FTE", "12 FTE", "8 FTE", "6 FTE", "3 FTE"],
        "Priority": ["High", "Critical", "High", "Critical", "Medium"],
        "Risk Level": ["Low", "Medium", "Medium", "High", "Low"]
    })
    table6 = dataframe_to_table_data(
        key="implementation_guide",
        df=df6,
        caption="Implementation phase guidelines",
        show_index=False
    )
    one.db_manager.add_table(table6)
    print(f"  ✓ Added table: {table6.key}")
    
    # Appendix tables
    # Table 7: Component specs
    df7 = pd.DataFrame({
        "Component ID": ["COMP-001", "COMP-002", "COMP-003", "COMP-004", "COMP-005", "COMP-006"],
        "Type": ["Processor", "Memory", "Storage", "Network", "Controller", "Sensor"],
        "Capacity": ["3.5 GHz", "32 GB", "2 TB SSD", "10 Gbps", "Quad-Core", "Multi-Ch"],
        "Power (W)": [95, 15, 8, 25, 65, 5],
        "Efficiency": ["92%", "95%", "98%", "90%", "88%", "94%"],
        "Cost (USD)": [450, 180, 220, 350, 280, 120]
    })
    table7 = dataframe_to_table_data(
        key="component_specs",
        df=df7,
        caption="Component specifications and characteristics",
        show_index=False
    )
    one.db_manager.add_table(table7)
    print(f"  ✓ Added table: {table7.key}")
    
    # Table 8: Raw data set 1
    df8 = pd.DataFrame({
        "Trial": [1, 2, 3, 4, 5, 6, 7, 8],
        "Temp (°C)": [25.3, 30.7, 28.4, 35.2, 26.8, 32.1, 29.5, 27.3],
        "Press (bar)": [2.1, 2.3, 2.0, 2.5, 2.2, 2.4, 2.1, 2.0],
        "Flow (L/h)": [125.4, 132.8, 118.6, 145.2, 128.3, 138.7, 122.9, 115.8],
        "Output": [87.2, 89.5, 85.3, 91.8, 88.1, 90.2, 86.7, 84.9],
        "Notes": ["Normal", "Normal", "Normal", "Elevated", "Normal", "Normal", "Normal", "Below target"]
    })
    table8 = dataframe_to_table_data(
        key="raw_data_set1",
        df=df8,
        caption="Raw experimental data - Set 1",
        show_index=False
    )
    one.db_manager.add_table(table8)
    print(f"  ✓ Added table: {table8.key}")
    
    # Table 9: Raw data set 2
    df9 = pd.DataFrame({
        "Trial": [1, 2, 3, 4, 5, 6, 7, 8],
        "Viscosity (cP)": [12.5, 15.3, 11.8, 18.2, 13.7, 16.4, 12.9, 11.2],
        "pH": [7.2, 7.4, 7.1, 7.6, 7.3, 7.5, 7.2, 7.0],
        "Density (g/mL)": [1.045, 1.052, 1.038, 1.068, 1.048, 1.058, 1.042, 1.035],
        "Yield (%)": [92.3, 94.7, 88.5, 96.2, 91.8, 95.1, 89.9, 86.4],
        "Quality Score": ["A", "A+", "B+", "A+", "A", "A+", "A-", "B"]
    })
    table9 = dataframe_to_table_data(
        key="raw_data_set2",
        df=df9,
        caption="Raw experimental data - Set 2",
        show_index=False
    )
    one.db_manager.add_table(table9)
    print(f"  ✓ Added table: {table9.key}")
    
    # Table 10: Algorithm performance
    df10 = pd.DataFrame({
        "Algorithm": ["Algorithm A", "Algorithm B", "Algorithm C", "Algorithm D", "Algorithm E"],
        "Time (ms)": [125, 89, 156, 203, 98],
        "Memory (MB)": [256, 512, 128, 1024, 384],
        "Accuracy (%)": [98.5, 96.3, 99.2, 97.8, 98.9],
        "Complexity": ["O(n log n)", "O(n²)", "O(n log n)", "O(n³)", "O(n log n)"],
        "Scalability": ["Excellent", "Good", "Excellent", "Fair", "Excellent"]
    })
    table10 = dataframe_to_table_data(
        key="algorithm_performance",
        df=df10,
        caption="Algorithm performance comparison",
        show_index=False
    )
    one.db_manager.add_table(table10)
    print(f"  ✓ Added table: {table10.key}")


def main():
    """Main function to populate the database."""
    
    print("=" * 70)
    print("Populating doc_lorum Database with Plots and Tables")
    print("=" * 70)
    print()
    
    # Set up paths
    source_dir = Path(__file__).parent
    work_dir = Path("temp") / "doc_lorum_work"
    
    # Initialize OneDoc
    print(f"Initializing OneDoc...")
    print(f"  Source: {source_dir}")
    print(f"  Work dir: {work_dir}")
    
    one = OneDoc(source_dir=source_dir, work_dir=work_dir)
    
    db_location = source_dir / "data.db"
    print(f"  Database: {db_location}")
    print()
    
    # Create all plots
    create_plots(one)
    
    # Create all tables
    create_tables(one)
    
    # Summary
    print()
    print("=" * 70)
    print("Database Population Complete!")
    print("=" * 70)
    print()
    print(f"Total plots added: {len(one.db_manager.list_plots())}")
    print(f"Total tables added: {len(one.db_manager.list_tables())}")
    print()
    print("Plots in database:")
    for plot_key in one.db_manager.list_plots():
        print(f"  - {plot_key}")
    print()
    print("Tables in database:")
    for table_key in one.db_manager.list_tables():
        print(f"  - {table_key}")
    print()
    print(f"Database location: {db_location}")
    print()
    print("Next steps:")
    print("  1. Update markdown files to use {{__key__}} syntax")
    print("  2. Run test_document.py to compile the document")
    
    # Close database
    one.db_manager.close()


if __name__ == "__main__":
    main()

