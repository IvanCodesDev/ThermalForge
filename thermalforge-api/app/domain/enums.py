from enum import StrEnum


class TaskStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    AWAITING_INPUT = "awaiting_input"
    BRIEFING = "briefing"
    THERMAL_ANALYSIS = "thermal_analysis"
    CONCEPT_IMAGING = "concept_imaging"
    MULTIVIEW_IMAGING = "multiview_imaging"
    MULTIVIEW_REVIEW = "multiview_review"
    MODELING = "modeling"
    MODEL_REVIEW = "model_review"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(StrEnum):
    SOURCE_DOCUMENT = "source_document"
    PARSED_DOCUMENT = "parsed_document"
    ENGINEERING_BRIEF = "engineering_brief"
    THERMAL_ANALYSIS = "thermal_analysis"
    THERMAL_DESIGN = "thermal_design"
    CONCEPT_IMAGE = "concept_image"
    MULTIVIEW_IMAGE = "multiview_image"
    RAW_MODEL = "raw_model"
    NORMALIZED_MODEL = "normalized_model"
    REPORT = "report"


class QualityStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
