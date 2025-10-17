# Paradoc Guidelines

You are an expert in Python and scalable web application development. 
You write secure, maintainable, and performant code following Fastapi and Python best practices.
You always perform tests at the end of each development cycle to ensure that you haven't introduced any bugs. 

## Technology Stack

Paradoc is a thin python wrapper around pandoc. It provides functionality for variable substitution in markdown files
and some additional formatting tweaks to ensure better output when exporting to .docx format.

### Python library Paradoc

In addition to wrap conversion capabilities around pandoc, paradoc also provides a websocket server that can be used to
stream converted html documents to a frontend document reader app.

### Frontend
* TailwindCSS 4
* Typescript
* React
* vite
* nodejs

#### Functional requirements
The frontend is a single page document reader app. 
The frontend shall have a websocket client running in a background thread listening for new html documents. 
The websocket server receives html content which are documents from pandoc converted html from markdown. 

#### Style guide

* All components should be styled using TailwindCSS
* All clickable buttons should use cursor-pointer

## Development Environment Setup

All dependencies and tasks are handled by `pixi` in a pyproject.toml file. 
There's a prod and test environment.

There is a `pixi run test` command that runs the pytest test suite.

To run a specific integration test, use `pixi run test -k test_name`
Or if you want to test the quetz backend tests you can run `pixi run qtest` which points to the tests located in
[quetz/tests](quetz/tests)

## Project Structure

```
.github/
.junie/
docs/
src/paradoc
frontend/
tests/
pyproject.toml
```