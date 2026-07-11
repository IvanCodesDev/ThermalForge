from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile

import filetype
import fitz
from charset_normalizer import from_bytes
from PIL import Image, UnidentifiedImageError

from app.domain.errors import (
    EncryptedDocument,
    InvalidDocument,
    UnsupportedDocumentType,
    UploadTooLarge,
)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True, slots=True)
class ValidatedDocument:
    path: Path
    filename: str
    extension: str
    mime_type: str
    size_bytes: int
    sha256: str


class DocumentValidator:
    _mime_by_extension = {
        ".pdf": "application/pdf",
        ".docx": DOCX_MIME,
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    _generic_mime_types = {"", "application/octet-stream"}
    _executable_signatures = (
        b"MZ",
        b"\x7fELF",
        b"\xfe\xed\xfa",
        b"\xcf\xfa\xed\xfe",
    )

    def __init__(
        self,
        *,
        max_upload_bytes: int,
        max_archive_entries: int,
        max_archive_uncompressed_bytes: int,
        max_image_pixels: int,
        max_archive_ratio: int = 200,
    ) -> None:
        self._max_upload_bytes = max_upload_bytes
        self._max_archive_entries = max_archive_entries
        self._max_archive_uncompressed_bytes = max_archive_uncompressed_bytes
        self._max_image_pixels = max_image_pixels
        self._max_archive_ratio = max_archive_ratio

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _validate_declared_mime(
        self,
        *,
        extension: str,
        declared_mime: str | None,
    ) -> str:
        expected = self._mime_by_extension[extension]
        declared = (declared_mime or "").lower().split(";", maxsplit=1)[0].strip()
        accepted = {expected, *self._generic_mime_types}
        if extension == ".md":
            accepted.add("text/plain")
        if declared not in accepted:
            raise UnsupportedDocumentType()
        return expected

    def _validate_pdf(self, path: Path) -> None:
        try:
            document = fitz.open(path)
        except (fitz.FileDataError, RuntimeError) as error:
            raise InvalidDocument("PDF is damaged or cannot be parsed.") from error

        try:
            if document.needs_pass:
                raise EncryptedDocument()
            if document.page_count == 0:
                raise InvalidDocument("PDF does not contain any pages.")
        finally:
            document.close()

    def _validate_docx(self, path: Path) -> None:
        if not is_zipfile(path):
            raise InvalidDocument("DOCX archive is damaged.")

        try:
            with ZipFile(path) as archive:
                members = archive.infolist()
                names = {member.filename for member in members}
                if len(members) > self._max_archive_entries:
                    raise InvalidDocument("DOCX contains too many archive entries.")
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise InvalidDocument("File is not a valid DOCX document.")
                if any(name.lower().endswith("vbaproject.bin") for name in names):
                    raise InvalidDocument("Macro-enabled Office documents are not accepted.")

                total_uncompressed = sum(member.file_size for member in members)
                total_compressed = sum(member.compress_size for member in members)
                if total_uncompressed > self._max_archive_uncompressed_bytes:
                    raise InvalidDocument("DOCX expands beyond the safe archive limit.")
                if total_compressed and (
                    total_uncompressed / total_compressed > self._max_archive_ratio
                ):
                    raise InvalidDocument("DOCX compression ratio exceeds the safe limit.")
        except BadZipFile as error:
            raise InvalidDocument("DOCX archive is damaged.") from error

    def _validate_image(self, path: Path, expected_mime: str) -> None:
        guessed = filetype.guess(path)
        if guessed is None or guessed.mime != expected_mime:
            raise UnsupportedDocumentType()

        try:
            with Image.open(path) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > self._max_image_pixels:
                    raise InvalidDocument("Image dimensions exceed the safe limit.")
                image.verify()
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
            raise InvalidDocument("Image is damaged or unsafe.") from error

    @staticmethod
    def _validate_text(path: Path) -> None:
        payload = path.read_bytes()
        if b"\x00" in payload:
            raise UnsupportedDocumentType()
        decoded = from_bytes(payload).best()
        if decoded is None:
            raise InvalidDocument("Text encoding could not be detected.")

    def validate(
        self,
        *,
        path: Path,
        original_filename: str,
        declared_mime: str | None,
    ) -> ValidatedDocument:
        size_bytes = path.stat().st_size
        if size_bytes == 0:
            raise InvalidDocument("Document is empty.")
        if size_bytes > self._max_upload_bytes:
            raise UploadTooLarge(self._max_upload_bytes)

        extension = Path(original_filename).suffix.lower()
        if extension not in self._mime_by_extension:
            raise UnsupportedDocumentType()

        with path.open("rb") as source:
            signature = source.read(16)
        if any(signature.startswith(candidate) for candidate in self._executable_signatures):
            raise UnsupportedDocumentType()

        expected_mime = self._validate_declared_mime(
            extension=extension,
            declared_mime=declared_mime,
        )
        if extension == ".pdf":
            if not signature.startswith(b"%PDF-"):
                raise UnsupportedDocumentType()
            self._validate_pdf(path)
        elif extension == ".docx":
            self._validate_docx(path)
        elif extension in {".png", ".jpg", ".jpeg", ".webp"}:
            self._validate_image(path, expected_mime)
        else:
            self._validate_text(path)

        return ValidatedDocument(
            path=path,
            filename=Path(original_filename).name,
            extension=extension,
            mime_type=expected_mime,
            size_bytes=size_bytes,
            sha256=self._hash_file(path),
        )
