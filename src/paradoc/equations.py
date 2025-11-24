from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List

from .common import MarkDownFile


@dataclass
class Equation:
    name: str
    func: Callable
    custom_eq_str_compiler: Callable = None
    add_link: bool = True
    include_python_code: bool = False
    md_instances: List[MarkDownFile] = field(default_factory=list)
    docx_instances: List[object] = field(default_factory=list)

    def to_latex(self, print_latex=False, print_formula=False, flags=None):
        if self.custom_eq_str_compiler is not None:
            return self.custom_eq_str_compiler(self.func)

        from inspect import getsource, getsourcelines

        import pytexit

        lines = getsourcelines(self.func)
        eq_latex = ""
        matches = ("def", "return", '"')
        dots = 0
        for line in lines[0]:
            if any(x in line for x in matches):
                dots += line.count('"')
                dots += line.count("'")
                continue
            if dots >= 6 or dots == 0:
                try:
                    eq_latex += pytexit.py2tex(line, print_latex=print_latex, print_formula=print_formula) + "\n"
                except Exception:
                    # Fallback: include the line as verbatim code to avoid crashing on pytexit quirks
                    # Escape special LaTeX characters
                    safe = line.strip().replace("\n", "")
                    if safe:
                        # Escape LaTeX special characters: \ must be first, then others
                        safe = safe.replace("\\", "\\textbackslash{}")
                        safe = safe.replace("_", "\\_")
                        safe = safe.replace("{", "\\{")
                        safe = safe.replace("}", "\\}")
                        safe = safe.replace("#", "\\#")
                        safe = safe.replace("$", "\\$")
                        safe = safe.replace("%", "\\%")
                        safe = safe.replace("&", "\\&")
                        safe = safe.replace("^", "\\textasciicircum{}")
                        safe = safe.replace("~", "\\textasciitilde{}")
                        eq_latex += f"\\texttt{{{safe}}}\n"
        eq_str = eq_latex

        if self.add_link:
            eq_str += f"{{#eq:{self.name}}}"

        if self.include_python_code:
            eq_str = f"\n\n```python\n{getsource(self.func)}\n```\n\n" + eq_str
        return eq_str
