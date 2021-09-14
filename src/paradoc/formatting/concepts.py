from dataclasses import dataclass


@dataclass
class TableFormat:
    style: str = "Grid Table 1 Light"
    font_size: float = 11
    font_style: str = "Arial"


@dataclass
class Formatting:
    is_appendix: bool
    paragraph_style_map: dict
    table_format: TableFormat
