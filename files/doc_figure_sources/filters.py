"""Project-level filters auto-discovered by paradoc at compile time.

This module is loaded by `paradoc.filters.discovery.discover_filters` when
present at the doc root. Every module-level `Filter` instance is
registered and becomes referenceable from markdown as `${ name.attr }`.
"""

from paradoc.filters import Filter, ScalarValue, TableView, attr


class EigenResultsDemo(Filter):
    """Hand-stubbed eigenvalue results for the demo doc.

    In a real project, this would read from a simulation output (driven
    by a Task). For the demo we return constants so the page renders
    without any solver installed.
    """

    @attr
    def first_freq(self) -> float:
        return 12.345

    @attr
    def frequency_table(self) -> TableView:
        # Points at a DB-backed table the demo populates separately.
        return TableView(table_key="eigen_freqs", display_kwargs={})

    @attr
    def damping(self) -> ScalarValue:
        return ScalarValue(value=0.012, units="-")


eig_main = EigenResultsDemo(name="eig_main")
