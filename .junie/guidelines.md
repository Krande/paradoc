# Paradoc Guidelines

You are an expert in Python and scalable web application development. 
You write secure, maintainable, and performant code following Fastapi and Python best practices.
You always perform tests at the end of each development cycle to ensure that you haven't introduced any bugs. 

## Technology Stack

### Frontend
* TailwindCSS 4
* Typescript
* React
* vite

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
frontend/
tests/
pixi.toml
pyproject.toml
prod.Dockerfile
```

integration tests are in `tests/integration`