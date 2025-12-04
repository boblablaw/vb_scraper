"""
PDF renderer for the Ultimate Guide.

This module keeps the rendering orchestration separate from data prep. It leans
on the existing section-building helpers inside `build_ultimate_guide` to avoid
changing output while making the pipeline easier to swap or extend later.
"""

from __future__ import annotations

from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

from ..layout import build_styles
from .sections import (
    build_cover_page,
    build_map_page,
    build_fit_score_table,
    build_travel_matrix,
    build_school_pages,
)


def build_story(core_module, styles):
    """
    Assemble the full story list using the section builders defined on the core module.
    """
    story = []
    build_cover_page(core_module, story, styles)
    build_map_page(core_module, story, styles)
    build_fit_score_table(core_module, story, styles)
    build_travel_matrix(core_module, story, styles)
    build_school_pages(core_module, story, styles)
    return story


def render_pdf(core_module):
    """
    Render the PDF using the prepared data inside the core module.
    """
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(core_module.OUTPUT_PDF),
        pagesize=letter,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.55 * inch,
    )
    story = build_story(core_module, styles)
    doc.build(story)
    return core_module.OUTPUT_PDF


__all__ = ["render_pdf", "build_story"]
