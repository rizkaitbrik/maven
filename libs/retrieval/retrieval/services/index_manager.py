"""SQLite FTS5-based index manager for fast content search."""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import NamedTuple
from retrieval.models.config import IndexConfig
from retrieval.services.content_extractor import ContentExtractor
from maven_logging import get_logger


class IndexedFile(NamedTuple):
    """Represents a file in the index."""
    id: int
    path: str
    file_name: str
    extension: str
    size: int
    modified_time: float
    content_hash: str
    indexed_at: float


class SearchMatch(NamedTuple):
    """Represents a search match from the index."""
    path: str
    snippet: str
    rank: float


class IndexManager:
    """Manages the SQLite FTS5 search index."""

    def __init__(self, config: IndexConfig, text_extensions: list[str]):
        """Initialize the index manager.
        
        Args:
            config: Index configuration
            text_extensions: List of text file extensions to index
        """
        self.config = config
        self.db_path = Path(config.db_path).expanduser()
        self.text_extensions = text_extensions
        self.content_extractor = ContentExtractor(text_extensions=text_extensions)
        self.logger = get_logger('retrieval.index')

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_schema()
        self.logger.debug("Index manager initialized", db_path=str(self.db_path))

    def _init_schema(self):
        """Initialize or upgrade the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS files
                         (
                             id            INTEGER PRIMARY KEY AUTOINCREMENT,
                             path          TEXT UNIQUE NOT NULL,
                             file_name     TEXT        NOT NULL,
                             extension     TEXT,
                             size          INTEGER,
                             modified_time REAL,
                             content_hash  TEXT,
                             indexed_at    REAL
                         )
                         """)

            # Create FTS5 virtual table for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS file_content USING fts5(
                    path UNINDEXED,
                    content,
                    tokenize='porter unicode61'
                )
            """)

            # Create metadata table
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS index_metadata
                         (
                             key   TEXT PRIMARY KEY,
                             value TEXT
                         )
                         """)

            # Store schema version
            conn.execute("""
                INSERT OR REPLACE INTO index_metadata (key, value)
                VALUES ('schema_version', '1')
            """)

            conn.commit()

    def _compute_hash(self, content: str) -> str:
        """Compute hash of file content."""
        return hashlib.sha256(content.encode('utf-8', errors='ignore')).hexdigest()

    def add_or_update_file(self, file_path: Path) -> bool:
        """Add or update a file in the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file was added/updated, False if skipped
        """
        # Extract content
        extracted = self.content_extractor.extract(file_path)
        if not extracted.success:
            self.logger.debug("Failed to extract content", path=str(file_path))
            return False

        # Check file size
        try:
            file_size = file_path.stat().st_size
            if file_size > self.config.max_file_size:
                self.logger.debug("File too large", path=str(file_path), size=file_size,
                                  max_size=self.config.max_file_size)
                return False
        except OSError as e:
            self.logger.debug("Failed to get file stats", path=str(file_path), error=str(e))
            return False

        # Compute hash and metadata
        content_hash = self._compute_hash(extracted.content)
        modified_time = file_path.stat().st_mtime
        indexed_at = datetime.now().timestamp()

        path_str = str(file_path.resolve())
        file_name = file_path.name
        extension = file_path.suffix.lower()

        with sqlite3.connect(self.db_path) as conn:
            # Check if file exists and hash matches
            cursor = conn.execute(
                "SELECT id, content_hash FROM files WHERE path = ?",
                (path_str,)
            )
            row = cursor.fetchone()

            if row:
                file_id, existing_hash = row
                if existing_hash == content_hash:
                    # Content hasn't changed, skip
                    self.logger.debug("File content unchanged, skipping", path=path_str)
                    return False

                # Update existing file
                self.logger.debug("Updating file in index", path=path_str)
                conn.execute("""
                             UPDATE files
                             SET file_name     = ?,
                                 extension     = ?,
                                 size          = ?,
                                 modified_time = ?,
                                 content_hash  = ?,
                                 indexed_at    = ?
                             WHERE id = ?
                             """, (file_name, extension, file_size, modified_time,
                                   content_hash, indexed_at, file_id))

                # Update FTS content
                conn.execute("""
                             DELETE
                             FROM file_content
                             WHERE path = ?
                             """, (path_str,))
                conn.execute("""
                             INSERT INTO file_content (path, content)
                             VALUES (?, ?)
                             """, (path_str, extracted.content))
            else:
                # Insert new file
                self.logger.debug("Adding new file to index", path=path_str)
                cursor = conn.execute("""
                                      INSERT INTO files (path, file_name, extension, size,
                                                         modified_time, content_hash, indexed_at)
                                      VALUES (?, ?, ?, ?, ?, ?, ?)
                                      """, (path_str, file_name, extension, file_size,
                                            modified_time, content_hash, indexed_at))

                # Insert FTS content
                conn.execute("""
                             INSERT INTO file_content (path, content)
                             VALUES (?, ?)
                             """, (path_str, extracted.content))

            conn.commit()
            return True

    def remove_file(self, file_path: Path) -> bool:
        """Remove a file from the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file was removed, False if not found
        """
        path_str = str(file_path.resolve())

        with sqlite3.connect(self.db_path) as conn:
            # Delete from files table
            cursor = conn.execute(
                "DELETE FROM files WHERE path = ?",
                (path_str,)
            )

            # Delete from FTS table
            conn.execute(
                "DELETE FROM file_content WHERE path = ?",
                (path_str,)
            )

            conn.commit()
            return cursor.rowcount > 0

    def search(self, query: str, limit: int = 100) -> list[SearchMatch]:
        """Search the index for matching files.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search matches with snippets
        """
        with sqlite3.connect(self.db_path) as conn:
            # Use FTS5 match with snippet and rank
            cursor = conn.execute("""
                                  SELECT path,
                                         snippet(file_content, 1, '→ ', '', '...', 40) as snippet,
                                         rank
                                  FROM file_content
                                  WHERE file_content MATCH ?
                                  ORDER BY rank
                                  LIMIT ?
                                  """, (query, limit))

            results = []
            for row in cursor.fetchall():
                results.append(SearchMatch(
                    path=row[0],
                    snippet=row[1],
                    rank=abs(row[2])  # FTS5 rank is negative, flip it
                ))

            return results

    def get_file_info(self, file_path: Path) -> IndexedFile | None:
        """Get information about an indexed file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            IndexedFile or None if not found
        """
        path_str = str(file_path.resolve())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                                  SELECT id,
                                         path,
                                         file_name,
                                         extension,
                                         size,
                                         modified_time,
                                         content_hash,
                                         indexed_at
                                  FROM files
                                  WHERE path = ?
                                  """, (path_str,))

            row = cursor.fetchone()
            if row:
                return IndexedFile(*row)
            return None

    def get_stats(self) -> dict:
        """Get index statistics.
        
        Returns:
            Dictionary with stats
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM files")
            file_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT SUM(size) FROM files")
            total_size = cursor.fetchone()[0] or 0

            cursor = conn.execute("SELECT MAX(indexed_at) FROM files")
            last_indexed = cursor.fetchone()[0]

            return {
                "file_count": file_count,
                "total_size_bytes": total_size,
                "last_indexed_at": last_indexed,
                "db_path": str(self.db_path),
            }

    def clear(self):
        """Clear all data from the index."""
        self.logger.info("Clearing index")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM files")
            conn.execute("DELETE FROM file_content")
            conn.commit()
        self.logger.info("Index cleared")

    def needs_reindex(self, file_path: Path) -> bool:
        """Check if a file needs to be re-indexed.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file needs reindexing
        """
        if not file_path.exists():
            return False

        indexed_file = self.get_file_info(file_path)
        if not indexed_file:
            return True

        try:
            current_mtime = file_path.stat().st_mtime
            return current_mtime > indexed_file.modified_time
        except OSError:
            return False
