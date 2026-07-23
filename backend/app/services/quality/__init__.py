"""
Quality Assessment Engine.

This package provides a modular, multi-provider image quality assessment
subsystem for PhotoMind AI.  It is a cross-cutting service designed to be
consumed by the recommendation engine, duplicate ranker, best-shot selector,
album cover selection, analytics, and search quality filters.

Quick start
-----------
    from app.services.quality import QualityService

    service = QualityService.default()
    with Image.open(path) as img:
        assessment = service.evaluate(img)

    print(assessment.quality_grade)   # QualityGrade.GOOD
    print(assessment.issues)          # []

Integration note
----------------
Future integration points (not in this sprint):
  • worker.py  → call evaluate() after thumbnail generation; persist
                 QualityAssessment fields to image_ai_analysis.keywords
  • recommendations/page.tsx  → read quality_grade + issues for filtering
  • analytics   → aggregate quality_grade distribution
"""

from .quality_service import QualityService
from .models import QualityAssessment, QualityGrade, QualityIssue, QualityConfig

__all__ = [
    "QualityService",
    "QualityAssessment",
    "QualityGrade",
    "QualityIssue",
    "QualityConfig",
]
