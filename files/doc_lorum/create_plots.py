"""
Script to generate placeholder images for the doc_lorum documentation using plotly
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.io._kaleido import get_chrome
from plotly.subplots import make_subplots

get_chrome()

# Set up output directories
main_images = Path(r"C:\Work\code\paradoc\files\doc_lorum\00-main\images")
appendix_images = Path(r"/files/doc_lorum/01-app\images")

# Create directories
main_images.mkdir(parents=True, exist_ok=True)
appendix_images.mkdir(parents=True, exist_ok=True)

print("Creating images with plotly...")

# Generate plot1.png - Historical trends
years = np.arange(2015, 2025)
trend = 50 + 5 * (years - 2015) + np.random.randn(10) * 3
df1 = pd.DataFrame({"Year": years, "Performance Index": trend})
fig = px.line(df1, x="Year", y="Performance Index", markers=True, title="Historical Trends Analysis")
fig.update_layout(template="plotly_white")
fig.write_image(str(main_images / "plot1.png"), width=1000, height=600)
print("Created plot1.png")

# Generate plot2.png - Data framework
categories = ["Collection", "Processing", "Analysis", "Validation", "Storage"]
values = [85, 92, 88, 95, 90]
df2 = pd.DataFrame({"Category": categories, "Efficiency": values})
fig = px.bar(df2, y="Category", x="Efficiency", orientation="h", title="Data Collection Framework Efficiency")
fig.update_layout(xaxis_range=[0, 100], template="plotly_white")
fig.write_image(str(main_images / "plot2.png"), width=1000, height=600)
print("Created plot2.png")

# Generate plot3.png - Statistical workflow
steps = ["Raw Data", "Preprocessing", "Statistical\nTests", "Model\nFitting", "Validation", "Results"]
completeness = [100, 98, 95, 92, 96, 94]
df3 = pd.DataFrame({"Step": steps, "Completeness": completeness})
fig = px.line(df3, x="Step", y="Completeness", markers=True, title="Statistical Analysis Workflow")
fig.update_layout(yaxis_range=[80, 105], template="plotly_white")
fig.write_image(str(main_images / "plot3.png"), width=1000, height=600)
print("Created plot3.png")

# Generate plot4.png - Primary results
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
fig = px.scatter(df4, x="Parameter X", y="Response", color="Condition", title="Primary Experimental Results and Trends")
fig.update_layout(template="plotly_white")
fig.write_image(str(main_images / "plot4.png"), width=1000, height=600)
print("Created plot4.png")

# Generate plot5.png - Comparative analysis
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
fig = px.bar(
    df5, x="Condition", y="Score", color="Group", barmode="group", title="Comparative Analysis Across Conditions"
)
fig.update_layout(template="plotly_white")
fig.write_image(str(main_images / "plot5.png"), width=1000, height=600)
print("Created plot5.png")

# Generate plot6.png - Error analysis
errors = np.random.normal(0, 2, 1000)
df6 = pd.DataFrame({"Error": errors})
fig = px.histogram(df6, x="Error", nbins=40, title="Error Distribution and Uncertainty Analysis")
fig.update_layout(template="plotly_white")
fig.write_image(str(main_images / "plot6.png"), width=1000, height=600)
print("Created plot6.png")

# Generate plot7.png - Theory comparison
x = np.linspace(0, 10, 100)
theoretical = 50 + 20 * np.exp(-x / 5) * np.sin(2 * x)
experimental = theoretical + np.random.randn(100) * 3
df7 = pd.DataFrame({"Input Parameter": x, "Theoretical": theoretical, "Experimental": experimental})
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=df7["Input Parameter"], y=df7["Theoretical"], mode="lines", name="Theoretical Prediction", line=dict(width=3)
    )
)
fig.add_trace(
    go.Scatter(
        x=df7["Input Parameter"],
        y=df7["Experimental"],
        mode="markers",
        name="Experimental Data",
        marker=dict(size=6, opacity=0.6),
    )
)
fig.update_layout(
    title="Theory vs Experiment Comparison",
    xaxis_title="Input Parameter",
    yaxis_title="Output Response",
    template="plotly_white",
)
fig.write_image(str(main_images / "plot7.png"), width=1000, height=600)
print("Created plot7.png")

# Appendix images
# Generate arch1.png - System architecture (text-based diagram)
layers = ["User Interface Layer", "Application Layer", "Business Logic Layer", "Data Access Layer", "Database Layer"]
y_positions = list(range(len(layers)))
fig = go.Figure()
for i, layer in enumerate(layers):
    fig.add_shape(
        type="rect",
        x0=0,
        y0=i - 0.4,
        x1=1,
        y1=i + 0.4,
        line=dict(color="black", width=2),
        fillcolor=px.colors.qualitative.Plotly[i],
    )
    fig.add_annotation(x=0.5, y=i, text=layer, showarrow=False, font=dict(size=14, color="white"))
fig.update_layout(
    title="System Architecture Diagram",
    xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    height=700,
    width=1000,
    template="plotly_white",
)
fig.write_image(str(appendix_images / "arch1.png"), width=1000, height=700)
print("Created arch1.png")

# Generate bench1.png - Performance benchmarks
configs = ["Config A", "Config B", "Config C", "Config D", "Config E"]
throughput = [1250, 1450, 1380, 1520, 1290]
latency = [25, 18, 22, 15, 28]
df_bench = pd.DataFrame({"Configuration": configs, "Throughput": throughput, "Latency": latency})
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(
    go.Bar(x=df_bench["Configuration"], y=df_bench["Throughput"], name="Throughput (ops/sec)"), secondary_y=False
)
fig.add_trace(
    go.Scatter(
        x=df_bench["Configuration"],
        y=df_bench["Latency"],
        name="Latency (ms)",
        mode="lines+markers",
        line=dict(width=3),
    ),
    secondary_y=True,
)
fig.update_layout(title="Performance Benchmarks", template="plotly_white")
fig.update_yaxes(title_text="Throughput (ops/sec)", secondary_y=False)
fig.update_yaxes(title_text="Latency (ms)", secondary_y=True)
fig.write_image(str(appendix_images / "bench1.png"), width=1000, height=600)
print("Created bench1.png")

# Generate timeseries1.png
time = np.arange(0, 100)
param1 = 50 + 10 * np.sin(time / 5) + np.random.randn(100) * 2
param2 = 60 + 8 * np.cos(time / 7) + np.random.randn(100) * 1.5
param3 = 55 + 5 * np.sin(time / 10) + np.random.randn(100) * 1
df_ts = pd.DataFrame({"Time": time, "Parameter 1": param1, "Parameter 2": param2, "Parameter 3": param3})
fig = go.Figure()
for col in ["Parameter 1", "Parameter 2", "Parameter 3"]:
    fig.add_trace(go.Scatter(x=df_ts["Time"], y=df_ts[col], mode="lines", name=col, line=dict(width=2)))
fig.update_layout(
    title="Time Series Analysis of Key Parameters",
    xaxis_title="Time (minutes)",
    yaxis_title="Value",
    template="plotly_white",
)
fig.write_image(str(appendix_images / "timeseries1.png"), width=1200, height=600)
print("Created timeseries1.png")

# Generate simulation1.png
iterations = np.arange(0, 500)
convergence = 100 * (1 - np.exp(-iterations / 100))
df_sim = pd.DataFrame({"Iteration": iterations, "Convergence": convergence})
fig = px.line(df_sim, x="Iteration", y="Convergence", title="Computational Simulation Convergence")
fig.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="Target (95%)")
fig.update_layout(yaxis_range=[0, 105], template="plotly_white")
fig.write_image(str(appendix_images / "simulation1.png"), width=1000, height=600)
print("Created simulation1.png")

# Generate heatmap1.png - Correlation matrix
np.random.seed(42)
variables = ["Var A", "Var B", "Var C", "Var D", "Var E", "Var F"]
n = len(variables)
correlation_matrix = np.random.randn(n, n) * 0.5
correlation_matrix = (correlation_matrix + correlation_matrix.T) / 2
np.fill_diagonal(correlation_matrix, 1)
correlation_matrix = np.clip(correlation_matrix, -1, 1)
df_corr = pd.DataFrame(correlation_matrix, columns=variables, index=variables)
fig = px.imshow(
    df_corr,
    text_auto=".2f",
    aspect="auto",
    color_continuous_scale="RdBu_r",
    zmin=-1,
    zmax=1,
    title="Correlation Matrix Heatmap",
)
fig.write_image(str(appendix_images / "heatmap1.png"), width=1000, height=800)
print("Created heatmap1.png")

# Generate dist1.png - Distribution plots
data_list = []
for i in range(6):
    param_data = np.random.normal(80 + i * 2, 5 + i * 0.5, 500)
    data_list.append(pd.DataFrame({"Parameter": f"Parameter {chr(65+i)}", "Value": param_data}))
df_dist = pd.concat(data_list, ignore_index=True)
fig = px.histogram(
    df_dist,
    x="Value",
    color="Parameter",
    facet_col="Parameter",
    facet_col_wrap=3,
    nbins=30,
    title="Parameter Distribution Plots",
)
fig.update_layout(template="plotly_white", height=800)
fig.write_image(str(appendix_images / "dist1.png"), width=1400, height=800)
print("Created dist1.png")

# Generate surface1.png - 3D surface plot
x = np.linspace(-5, 5, 30)
y = np.linspace(-5, 5, 30)
X, Y = np.meshgrid(x, y)
Z = np.sin(np.sqrt(X**2 + Y**2)) * 10 + 50
fig = go.Figure(data=[go.Surface(x=X, y=Y, z=Z, colorscale="Viridis")])
fig.update_layout(
    title="3D Surface Plot - Interaction Effects",
    scene=dict(xaxis_title="Factor X", yaxis_title="Factor Y", zaxis_title="Response Z"),
    template="plotly_white",
)
fig.write_image(str(appendix_images / "surface1.png"), width=1000, height=800)
print("Created surface1.png")

# Generate qc1.png - QC workflow
steps = ["Data Input", "Initial Validation", "Outlier Detection", "Range Check", "Consistency Test", "Final Approval"]
y_positions = list(range(len(steps)))
fig = go.Figure()
for i, step in enumerate(steps):
    color = "lightgreen" if i < len(steps) - 1 else "lightblue"
    fig.add_shape(
        type="rect", x0=0.25, y0=i - 0.35, x1=0.75, y1=i + 0.35, line=dict(color="black", width=2), fillcolor=color
    )
    fig.add_annotation(x=0.5, y=i, text=step, showarrow=False, font=dict(size=12, color="black"))
fig.update_layout(
    title="Quality Control Workflow",
    xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    height=800,
    width=1000,
    template="plotly_white",
)
fig.write_image(str(appendix_images / "qc1.png"), width=1000, height=800)
print("Created qc1.png")

print("\n✓ All images created successfully!")
print(f"Main images: {len(list(main_images.glob('*.png')))} files in {main_images}")
print(f"Appendix images: {len(list(appendix_images.glob('*.png')))} files in {appendix_images}")
