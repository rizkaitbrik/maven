from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class DocumentMetadata:
    id: str
    path: str
    filename: str
    extension: str
    indexed_at: datetime = field(default_factory=datetime.now)
    modified_at: Optional[datetime] = None
    language: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    char_count: Optional[int] = None
    title: Optional[str] = None
    source: Optional[str] = None

    @classmethod
    def from_path(cls, path: str, doc_id: Optional[str]) -> "DocumentMetadata":
        path = Path(path).resolve()
        stat = path.stat() if path.exists() else None

        return cls(
            id=doc_id or cls._generate_id(path),
            path=str(path),
            filename=path.name,
            extension=path.suffix.lstrip(".") if path.suffix else "",
            modified_at=datetime.fromtimestamp(stat.st_mtime) if stat else None,
            size_bytes=stat.st_size if stat else None,
            language=cls._detect_language(path)
        )

    @staticmethod
    def _generate_id(path: Path) -> str:
        import hashlib
        return hashlib.sha256(path.as_posix().encode()).hexdigest()[:32]

    @staticmethod
    def _detect_language(path: Path) -> Optional[str]:
        # Placeholder for language detection logic
        ext_map =