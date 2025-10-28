"""Proxy for Word document operations in isolated process mode.

This module provides a proxy that records document operations and executes
them in an isolated process to suppress C stack error logs.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union, Literal, Any

from .wrapper import CaptionReference, FigureLayout


@dataclass
class DocumentOperation:
    """Represents a single document operation to be replayed."""
    operation: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    result_id: Optional[int] = None  # For operations that return values


class IsolatedWordDocument:
    """Proxy for WordDocument that records operations for isolated execution.

    This class has the same interface as WordDocument but records all operations
    instead of executing them immediately. The operations are executed in an
    isolated process when save() is called.
    """

    def __init__(self, template: Optional[Union[str, Path]] = None, visible: bool = False):
        """Initialize isolated document proxy.

        Args:
            template: Optional template path
            visible: Whether Word should be visible
        """
        self._template = str(template) if template else None
        self._visible = visible
        self._operations = []
        self._next_result_id = 0
        self._figure_count = 0
        self._table_count = 0
        self._saved_path = None

    def _record_operation(self, operation: str, *args, return_value: Any = None, **kwargs) -> Any:
        """Record an operation for later execution.

        Args:
            operation: Name of the operation
            *args: Positional arguments
            return_value: Value to return immediately (for operations that return values)
            **kwargs: Keyword arguments

        Returns:
            The return_value if provided
        """
        result_id = None
        if return_value is not None:
            result_id = self._next_result_id
            self._next_result_id += 1

        self._operations.append(DocumentOperation(
            operation=operation,
            args=args,
            kwargs=kwargs,
            result_id=result_id
        ))

        return return_value

    def add_heading(self, text: str, level: int = 1):
        """Record add_heading operation."""
        self._record_operation("add_heading", text, level)

    def add_paragraph(self, text: str = "", style: str = "Normal"):
        """Record add_paragraph operation."""
        self._record_operation("add_paragraph", text, style)

    def add_text(self, text: str):
        """Record add_text operation."""
        self._record_operation("add_text", text)

    def add_page_break(self):
        """Record add_page_break operation."""
        self._record_operation("add_page_break")

    def add_section_break(self, break_type: Literal["next_page", "continuous", "even_page", "odd_page"] = "next_page"):
        """Record add_section_break operation."""
        self._record_operation("add_section_break", break_type)

    def add_figure_with_caption(
        self,
        caption_text: str,
        image_path: Optional[Union[str, Path]] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        layout: Union[FigureLayout, str] = FigureLayout.INLINE,
        create_bookmark: bool = True,
        use_chapter_numbers: bool = True,
    ) -> Optional[CaptionReference]:
        """Record add_figure_with_caption operation and return a placeholder reference."""
        # Convert layout to string for serialization
        layout_str = layout.value if isinstance(layout, FigureLayout) else layout

        # Create a placeholder reference that will be valid when executed
        ref = None
        if create_bookmark:
            ref = CaptionReference(
                bookmark_name=f"_placeholder_fig_{self._figure_count}",
                id=self._figure_count,
                reference_type="figure"
            )
            self._figure_count += 1

        self._record_operation(
            "add_figure_with_caption",
            caption_text=caption_text,
            image_path=str(image_path) if image_path else None,
            width=width,
            height=height,
            layout=layout_str,
            create_bookmark=create_bookmark,
            use_chapter_numbers=use_chapter_numbers,
            return_value=ref
        )

        return ref

    def add_table_with_caption(
        self,
        caption_text: str,
        rows: int = 2,
        cols: int = 2,
        data: Optional[list[list]] = None,
        create_bookmark: bool = True,
        use_chapter_numbers: bool = True,
    ) -> Optional[CaptionReference]:
        """Record add_table_with_caption operation and return a placeholder reference."""
        # Create a placeholder reference that will be valid when executed
        ref = None
        if create_bookmark:
            ref = CaptionReference(
                bookmark_name=f"_placeholder_tbl_{self._table_count}",
                id=self._table_count,
                reference_type="table"
            )
            self._table_count += 1

        self._record_operation(
            "add_table_with_caption",
            caption_text=caption_text,
            rows=rows,
            cols=cols,
            data=data,
            create_bookmark=create_bookmark,
            use_chapter_numbers=use_chapter_numbers,
            return_value=ref
        )

        return ref

    def add_cross_reference(
        self,
        bookmark_name: Union[CaptionReference, str, int],
        reference_type: Optional[Literal["figure", "table"]] = None,
        include_hyperlink: bool = True,
        prefix_text: str = "",
        include_caption_text: bool = False,
    ):
        """Record add_cross_reference operation."""
        # Convert CaptionReference to serializable form
        if isinstance(bookmark_name, CaptionReference):
            bookmark_data = {
                "bookmark_name": bookmark_name.bookmark_name,
                "id": bookmark_name.id,
                "reference_type": bookmark_name.reference_type
            }
        else:
            bookmark_data = bookmark_name

        self._record_operation(
            "add_cross_reference",
            bookmark_data,
            reference_type,
            include_hyperlink,
            prefix_text,
            include_caption_text
        )

    def update_fields(self):
        """Record update_fields operation."""
        self._record_operation("update_fields")

    def save(self, path: Union[str, Path]):
        """Execute all recorded operations in an isolated process and save.

        Args:
            path: Path where to save the document
        """
        from .isolated import run_word_operation_isolated

        self._saved_path = str(Path(path).absolute())

        # Run all operations in isolated process
        success, result, message = run_word_operation_isolated(
            _execute_document_operations,
            self._template,
            self._visible,
            self._operations,
            self._saved_path,
            timeout_s=120.0,
            redirect_stdout=False
        )

        if not success:
            raise RuntimeError(f"Failed to save document in isolated process: {message}")

    def close(self, save_changes: bool = False):
        """Close operation - no-op in isolated mode since document is already closed."""
        pass

    def get_bookmark_names(self) -> list[str]:
        """Get bookmark names - returns placeholder names in isolated mode."""
        return [f"_placeholder_fig_{i}" for i in range(self._figure_count)] + \
               [f"_placeholder_tbl_{i}" for i in range(self._table_count)]

    @property
    def com_document(self):
        """Not available in isolated mode."""
        raise NotImplementedError("com_document not available in isolated mode")

    @property
    def com_application(self):
        """Not available in isolated mode."""
        raise NotImplementedError("com_application not available in isolated mode")


def _execute_document_operations(
    template: Optional[str],
    visible: bool,
    operations: list[DocumentOperation],
    output_path: str
) -> str:
    """Worker function that executes recorded operations in isolated process.

    Args:
        template: Optional template path
        visible: Whether Word should be visible
        operations: List of operations to execute
        output_path: Where to save the document

    Returns:
        The output path
    """
    # Import here since this runs in isolated process
    from .wrapper import WordApplication, CaptionReference, FigureLayout

    # Print to stdout (will be captured if redirect_stdout=True)
    print(f"\nExecuting {len(operations)} operations in isolated process...")

    with WordApplication(visible=visible, run_isolated=False) as word_app:
        doc = word_app.create_document(template=template)

        # Map to store references created during execution
        reference_map = {}

        for i, op in enumerate(operations):
            try:
                if op.operation == "add_heading":
                    doc.add_heading(*op.args)

                elif op.operation == "add_paragraph":
                    doc.add_paragraph(*op.args)

                elif op.operation == "add_text":
                    doc.add_text(*op.args)

                elif op.operation == "add_page_break":
                    doc.add_page_break()

                elif op.operation == "add_section_break":
                    doc.add_section_break(*op.args)

                elif op.operation == "add_figure_with_caption":
                    # Convert layout string back to enum
                    kwargs = dict(op.kwargs)
                    if "layout" in kwargs and isinstance(kwargs["layout"], str):
                        kwargs["layout"] = FigureLayout(kwargs["layout"])

                    ref = doc.add_figure_with_caption(**kwargs)
                    if op.result_id is not None:
                        reference_map[op.result_id] = ref

                elif op.operation == "add_table_with_caption":
                    ref = doc.add_table_with_caption(**op.kwargs)
                    if op.result_id is not None:
                        reference_map[op.result_id] = ref

                elif op.operation == "add_cross_reference":
                    # Reconstruct CaptionReference if needed
                    bookmark_data = op.args[0]
                    if isinstance(bookmark_data, dict):
                        bookmark_ref = CaptionReference(**bookmark_data)
                        doc.add_cross_reference(
                            bookmark_ref,
                            *op.args[1:],
                            **op.kwargs
                        )
                    else:
                        doc.add_cross_reference(*op.args, **op.kwargs)

                elif op.operation == "update_fields":
                    doc.update_fields()

                else:
                    print(f"Warning: Unknown operation: {op.operation}", file=sys.stderr)

            except Exception as e:
                print(f"Error executing operation {i} ({op.operation}): {e}", file=sys.stderr)
                raise

        # Save the document
        doc.save(output_path)

    print(f"Document saved to {output_path}")
    return output_path

