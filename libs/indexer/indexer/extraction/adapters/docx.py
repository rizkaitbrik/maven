"""DOCX extractor using LangChain's document loaders."""

from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader
from libs.indexer.indexer.extraction.models.extraction_result import ExtractionResult


class DocxExtractor:
    """Extracts content from DOCX files.

    Uses docx2txt via LangChain for Word document parsing.

    Usage:
        extractor = DocxExtractor()
        result = extractor.extract("document.docx")
        print(result.text)
    """

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}

    def __init__(self):
        """Initialize the DOCX extractor."""
        pass

    @property
    def name(self) -> str:
        return "DocxExtractor"

    def supports(self, file_path: Path | str) -> bool:
        """Check if file is a Word document."""
        path = Path(file_path)
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, file_path: Path | str) -> ExtractionResult:
        """Extract content from a DOCX file.

        Args:
            file_path: Path to the DOCX file

        Returns:
            ExtractionResult with text and metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a file
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise ValueError(f"Not a file: {path}")

        # Use Docx2txtLoader
        loader = Docx2txtLoader(str(path))
        documents = loader.load()

        # Combine all content
        full_text = "\n\n".join(doc.page_content for doc in documents)

        # Try to extract images using python-docx
        images = self._extract_images(path)

        return ExtractionResult(
            text=full_text,
            images=images,
            metadata={
                "extractor": self.name,
                "path": str(path.resolve()),
                "filename": path.name,
                "extension": path.suffix,
            },
        )

    def _extract_images(self, path: Path) -> list[bytes]:
        """Extract images from DOCX using python-docx."""
        try:
            from docx import Document

            images = []
            doc = Document(str(path))

            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    image_data = rel.target_part.blob
                    images.append(image_data)

            return images

        except Exception:
            return []