"""
Common types and utilities for Word document processing.

This module now serves as a re-export of the models module for backward compatibility.
The actual dataclass definitions have been moved to models.py for better organization.
"""

# Re-export the dataclasses from models.py for backward compatibility
from .models import DocXFigureRef, DocXTableRef

__all__ = ['DocXTableRef', 'DocXFigureRef']
