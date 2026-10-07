"""
SQLite Persistence Layer for JARVIS Memory.
Provides thread-safe relational storage and retrieval for long-term facts, preferences, and projects.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
import threading
from typing import List, Optional

from app.core.config import DATA_DIR
from app.core.logger import get_logger

logger = get_logger("memory.db")


@dataclass
class MemoryItem:
    """Represents a persisted long-term memory entry."""
    id: int
    category: str
    content: str
    importance: int
    created_at: str
    updated_at: str
    source_turn: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "content": self.content,
            "importance": self.importance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_turn": self.source_turn,
        }


class MemoryDatabase:
    """Thread-safe SQLite database manager for JARVIS memories."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (DATA_DIR / "jarvis_memory.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initializes tables and indexes."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        content TEXT NOT NULL,
                        importance INTEGER DEFAULT 3,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        source_turn TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)"
                )
                conn.commit()
                logger.info(f"Memory database initialized at {self.db_path}")

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: int = 3,
        source_turn: Optional[str] = None,
    ) -> MemoryItem:
        """Stores a new memory entry."""
        cleaned_content = content.strip()
        now = datetime.now().isoformat()

        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO memories (category, content, importance, created_at, updated_at, source_turn)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (category.lower(), cleaned_content, importance, now, now, source_turn),
                )
                conn.commit()
                mem_id = cur.lastrowid
                logger.info(f"Memory #{mem_id} added [{category}]: '{cleaned_content}'")
                return MemoryItem(
                    id=mem_id,
                    category=category.lower(),
                    content=cleaned_content,
                    importance=importance,
                    created_at=now,
                    updated_at=now,
                    source_turn=source_turn,
                )

    def get_memory(self, memory_id: int) -> Optional[MemoryItem]:
        """Retrieves a single memory by ID."""
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (memory_id,)
                ).fetchone()
                if row:
                    return MemoryItem(
                        id=row["id"],
                        category=row["category"],
                        content=row["content"],
                        importance=row["importance"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        source_turn=row["source_turn"],
                    )
                return None

    def get_all_memories(self, category: Optional[str] = None) -> List[MemoryItem]:
        """Returns all memories, optionally filtered by category."""
        with self._lock:
            with self._get_connection() as conn:
                if category:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE category = ? ORDER BY importance DESC, updated_at DESC",
                        (category.lower(),),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM memories ORDER BY importance DESC, updated_at DESC"
                    ).fetchall()

                return [
                    MemoryItem(
                        id=r["id"],
                        category=r["category"],
                        content=r["content"],
                        importance=r["importance"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                        source_turn=r["source_turn"],
                    )
                    for r in rows
                ]

    def update_memory(
        self,
        memory_id: int,
        content: str,
        category: Optional[str] = None,
        importance: Optional[int] = None,
    ) -> bool:
        """Updates an existing memory's content or properties."""
        now = datetime.now().isoformat()
        with self._lock:
            with self._get_connection() as conn:
                existing = self.get_memory(memory_id)
                if not existing:
                    return False

                new_category = (category or existing.category).lower()
                new_importance = importance if importance is not None else existing.importance

                conn.execute(
                    """
                    UPDATE memories
                    SET content = ?, category = ?, importance = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (content.strip(), new_category, new_importance, now, memory_id),
                )
                conn.commit()
                logger.info(f"Memory #{memory_id} updated")
                return True

    def delete_memory(self, memory_id: int) -> bool:
        """Deletes a specific memory entry."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                conn.commit()
                deleted = cur.rowcount > 0
                if deleted:
                    logger.info(f"Memory #{memory_id} deleted")
                return deleted

    def clear_all_memories(self) -> int:
        """Privacy function: wipes all stored memories."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("DELETE FROM memories")
                conn.commit()
                count = cur.rowcount
                logger.warning(f"All memories cleared ({count} records purged)")
                return count

    def search_memories(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Performs keyword relevance search across stored memories."""
        query_words = set(query.lower().split())
        # Remove small noise words
        stop_words = {"the", "is", "at", "which", "on", "a", "an", "and", "or", "to", "in", "for", "hai", "kya", "ko"}
        keywords = [w for w in query_words if len(w) > 2 and w not in stop_words]

        all_mems = self.get_all_memories()
        if not keywords:
            # If no meaningful keywords, return top importance items
            return all_mems[:limit]

        scored_mems = []
        for mem in all_mems:
            content_lower = mem.content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches > 0:
                score = (matches * 10) + mem.importance
                scored_mems.append((score, mem))

        scored_mems.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_mems[:limit]]


_db_instance: Optional[MemoryDatabase] = None


def get_memory_database(db_path: Optional[Path] = None) -> MemoryDatabase:
    """Singleton getter for memory database."""
    global _db_instance
    if _db_instance is None or db_path is not None:
        _db_instance = MemoryDatabase(db_path=db_path)
    return _db_instance
