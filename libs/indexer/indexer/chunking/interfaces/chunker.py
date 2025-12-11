from typing import Protocol, Any

from indexer.models.chunking import Chunk


class Chunker(Protocol):
    """Protocol for chunkers."""

    def chunk(
            self,
            text: str,
            doc_id: str,
            metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split text into chunks.

        Args:
            text: Text content to chunk
            doc_id: Parent document ID
            metadata: Metadata to attach to each chunk

        Returns:
            List of Chunk objects
        """
        ...