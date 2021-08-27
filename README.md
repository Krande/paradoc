# Paradoc

[![Anaconda-Server Badge](https://anaconda.org/krande/paradoc/badges/version.svg)](https://anaconda.org/krande/paradoc)
[![Anaconda-Server Badge](https://anaconda.org/krande/paradoc/badges/latest_release_date.svg)](https://anaconda.org/krande/paradoc)
[![Anaconda-Server Badge](https://anaconda.org/krande/paradoc/badges/platforms.svg)](https://anaconda.org/krande/paradoc)
[![Anaconda-Server Badge](https://anaconda.org/krande/paradoc/badges/downloads.svg)](https://anaconda.org/krande/paradoc)

A python library for parametric documentation based on markdown and pandoc. `paradoc` brings
some additional functionality to ensure improved end-formatting for .docx exports and integrating 
variable substitution. Use `{{__variable__}}` in your markdown files to insert any text prior to running pandoc.

Install using

```
conda install -c krande -c conda-forge paradoc
```

Note! This is still very early in development so expect things to break.


## Usage
 


## For developers

For developers interested in contributing to this project feel free to 
make a fork, experiment and create a pull request when you have something you 
would like to add/change/remove. 

Before making a pull request you need to lint with, isort, flake8 and black.
Assuming you have a cmd terminal open in the repo directory you can
run

````
pip install black isort flake8
isort .
flake8 .
black .
````

Or if you have make installed you can just run `make format` 
to run all three tools at once.

## Project Responsible ###

	Kristoffer H. Andersen