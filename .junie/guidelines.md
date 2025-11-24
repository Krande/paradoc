# Paradoc Guidelines

You are an expert in Python, web application development and Office Open XML (OOXML), more specifically the MS Word WordprocessingML. 
You always perform tests at the end of each development cycle to ensure that you haven't introduced any bugs. 

## Technology Stack

Paradoc is a thin python wrapper around pandoc. It provides functionality for variable substitution in markdown files
and some additional formatting tweaks to ensure better output when exporting to .docx format.

### Python library Paradoc

In addition to wrap conversion capabilities around pandoc (and using pandoc-crossref),
paradoc also provides a websocket server that can be used to
stream the document (streamed as AST JSON chunks and figures separately) to a frontend document reader app.

#### Export to .docx

The export to docx functionality is currently structured by converting md files 1 by 1 using `pandoc`,
then the python library `python-docx` and `docxcompose` (docxcompose source now part of paradoc copied to paradoc/io/word/compose).

### Frontend
* TailwindCSS 4
* Typescript
* React
* vite
* nodejs

#### Functional requirements
The frontend is a single page document reader app. 

#### Style guide

* All components should be styled using TailwindCSS
* All clickable buttons should use cursor-pointer

## Development Environment Setup

All dependencies and tasks are handled by `pixi` in a pyproject.toml file. 
There's a `prod` and `test` environment (see environment definitions in pyproject.toml)..

There is a `pixi run test` command that runs the pytest test suite.

To run arbitrary python commands you should do

```pixi run python -e prod -c "import plotly; import kaleido; print('Success')" 2>&1```

Or to run a python script

```pixi run -e prod python scripts/run_script.py```

To compile a standalone frontend.zip file

```pixi run wbuild```


## Project Structure

```
.github/
.junie/
docs/
files/
src/paradoc
frontend/
tests/
pyproject.toml
```

## OneDoc Default Document Structure

The document is structured in a Main and Appendix part. All heading in Main should be 1, 1.1, 1.2, ..., 2, 2.1, .. etc., while
Appendix should be Appendix A, A.1, A.2, ..., Appendix B, B1., ..., etc.
Figure, Table and Equation numbering should use the level 1 heading number then hyphen and the incremented
number per figure within that level 1 heading section. The incremented number should be reset to 1 when a new level 1 heading is encountered.

Cross-reference should always include label and number.

## Copilot shell instructions
The default shell for agentic commands is powershell and the cwd is always the project root.

So under no circumstances should you use `cd` or `pwd` to change the cwd.
Or use characters such as && when trying to run commands in the shell
