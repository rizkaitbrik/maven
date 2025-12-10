"""PDF extractor using LangChain's document loaders."""

from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from indexer.extraction.models.extraction_result import ExtractionResult


class PDFExtractor:
    """Extracts content from PDF files.

    Uses PyMuPDF (fitz) via LangChain for fast, accurate PDF parsing.
    Extracts text, and can optionally extract images and tables.

    Usage:
        extractor = PDFExtractor()
        result = extractor.extract("document.pdf")
        print(result.text)
        print(result.metadata["page_count"])
    """

    SUPPORTED_EXTENSIONS = {".pdf"}

    def __init__(
            self,
            extract_images: bool = False,
    ):
        """Initialize the PDF extractor.

        Args:
            extract_images: Whether to extract images from PDFs
        """
        self._extract_images = extract_images

    @property
    def name(self) -> str:
        return "PDFExtractor"

    def supports(self, file_path: Path | str) -> bool:
        """Check if file is a PDF."""
        path = Path(file_path)
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, file_path: Path | str) -> ExtractionResult:
        """Extract content from a PDF file.

        Args:
            file_path: Path to the PDF file

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

        # Use PyMuPDFLoader for fast PDF parsing
        loader = PyMuPDFLoader(str(path))
        documents = loader.load()

        # Combine all pages
        pages_text = []
        for doc in documents:
            pages_text.append(doc.page_content)

        full_text = "\n\n".join(pages_text)

        return ExtractionResult(
            text=full_text,
            metadata={
                "extractor": self.name,
                "path": str(path.resolve()),
                "filename": path.name,
                "extension": path.suffix,
                "page_count": len(documents),
            },
        )

    @staticmethod
    def _extract_images_from_pdf(path: Path) -> list[bytes]:
        """Extract images from PDF using PyMuPDF directly."""
        try:
            import fitz  # PyMuPDF

            images = []
            doc = fitz.open(str(path))

            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    images.append(image_bytes)

            doc.close()
            return images

        except Exception:
            return []