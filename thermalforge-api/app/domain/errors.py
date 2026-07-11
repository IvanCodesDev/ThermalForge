class DomainError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class InvalidStateTransition(DomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            code="invalid_state_transition",
            message=f"Task cannot transition from {current} to {target}.",
            status_code=409,
        )


class SourceDocumentRequired(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="source_document_required",
            message="Task must contain at least one source document before it can start.",
            status_code=409,
        )


class TaskAlreadyStarted(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="task_already_started",
            message="Task input is closed because processing has already started.",
            status_code=409,
        )


class EntityNotFound(DomainError):
    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(
            code=f"{entity}_not_found",
            message=f"{entity.replace('_', ' ').title()} {entity_id} was not found.",
            status_code=404,
        )


class InvalidArtifactPath(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_artifact_path",
            message="Artifact path must remain inside the configured artifact root.",
            status_code=400,
        )


class ArtifactConflict(DomainError):
    def __init__(self, storage_uri: str) -> None:
        super().__init__(
            code="artifact_conflict",
            message=f"Artifact {storage_uri} already exists with different content.",
            status_code=409,
        )


class ViewerModelNotFound(DomainError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            code="viewer_model_not_found",
            message=f"No approved viewer model is available for task {task_id}.",
            status_code=404,
        )


class UnsupportedViewerModelFormat(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="unsupported_viewer_model_format",
            message="Viewer models must use STL, GLB, glTF, or OBJ format.",
            status_code=415,
        )


class ModelAssetUnavailable(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="model_asset_unavailable",
            message="The configured reference model assets are unavailable.",
            status_code=500,
            retryable=True,
        )


class UploadTooLarge(DomainError):
    def __init__(self, limit_bytes: int) -> None:
        super().__init__(
            code="upload_too_large",
            message=f"Document exceeds the {limit_bytes}-byte upload limit.",
            status_code=413,
        )


class UnsupportedDocumentType(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="unsupported_document_type",
            message="Document type is unsupported or does not match its content.",
            status_code=415,
        )


class InvalidDocument(DomainError):
    def __init__(self, message: str = "Document is empty, damaged, or unsafe.") -> None:
        super().__init__(
            code="invalid_document",
            message=message,
            status_code=422,
        )


class EncryptedDocument(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="encrypted_document",
            message="Encrypted PDFs must be unlocked before upload.",
            status_code=422,
        )


class DocumentProcessingFailed(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="document_processing_failed",
            message="Document parsing failed. Retry the parsing stage.",
            status_code=500,
            retryable=True,
        )


class InvalidLLMOutput(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_llm_output",
            message="The model returned constraints that could not be verified.",
            status_code=502,
            retryable=True,
        )


class LLMProviderUnavailable(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="llm_provider_unavailable",
            message="The configured LLM provider is unavailable.",
            status_code=503,
            retryable=True,
        )


class InvalidImageOutput(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_image_output",
            message="The image provider returned an invalid or oversized image.",
            status_code=502,
            retryable=True,
        )


class ImageProviderUnavailable(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="image_provider_unavailable",
            message="The configured image provider is unavailable.",
            status_code=503,
            retryable=True,
        )


class ClarificationNotFound(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="clarification_not_found",
            message="No unanswered clarification exists for this task.",
            status_code=404,
        )


class InvalidClarificationAnswer(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_clarification_answer",
            message="Clarification answer must contain meaningful text.",
            status_code=422,
        )


class InvalidThermalInput(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_thermal_input",
            message="Engineering constraints cannot form a valid thermal-analysis input.",
            status_code=422,
        )


class NoCompliantThermalSolution(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="no_compliant_thermal_solution",
            message="Every thermal solution violates a confirmed engineering constraint.",
            status_code=422,
        )
