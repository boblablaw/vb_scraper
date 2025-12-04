"""
Layout helpers for the Ultimate Guide PDF.

Right now this is intentionally thin: it centralizes style creation so we can
swap or extend styling in one place without touching the renderer or data
layers. Future iterations can add paragraph templates, table styles, and other
layout primitives here.
"""

from reportlab.lib.styles import getSampleStyleSheet


def build_styles():
    """
    Return a base stylesheet for the PDF.
    """
    return getSampleStyleSheet()


__all__ = ["build_styles"]
