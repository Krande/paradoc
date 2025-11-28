# Figure Sources for FEA Models

This document provides examples of figure source specifications for different FEA software formats.
The specifications include details such as the source file paths, output file paths, fields to visualize, and camera positions.

## CAD models

Here are different examples of CAD model figure sources.

<--
figure_source: cad_model_file
figure_title: Source CAD Model STEP Example
source_inp: c:\mymodel.stp
camera_pos: iso_3
-->

<--
figure_source: cad_model_file
figure_title: Source CAD Model IFC Example
source_inp: c:\mymodel.IFC
camera_pos: iso_3
-->

## Abaqus
<--
figure_source: fea_model
figure_title: Abaqus FEA Model Example
fea_format: abaqus
source_inp: c:\mymodel.inp
camera_pos: iso_3
-->

<--
figure_source: fea_model_results
figure_title: Abaqus FEA Model Example
fea_format: abaqus
source_inp: c:\mymodel.inp
output_file: c:\mymodel.odb
field: S
camera_pos: iso_3
-->

## Sesam
<--
figure_source: fea_model_results
figure_title: Sesam FEA Model Example
fea_format: sesam
source_inp: c:\mymodel.fem
output_file: c:\mymodel.sin
field: S
camera_pos: iso_3
-->

