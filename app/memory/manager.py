"""
High-Level Memory Coordinator for JARVIS.
Integrates extraction, database persistence, context retrieval, and user privacy controls.
"""

from pathlib import Path
from typing import List, Optional

from app.core.events import Event, EventBus, get_event_bus
from app.core.logger import get_logger
from app.memory.database import MemoryDatabase, MemoryItem, get_memory_database
from app.memory.extractor import ExtractedMemory, MemoryExtractor

logger = get_logger("memory.manager")


class MemoryManager:
    """Manages long-term user memory extraction, storage, and contextual retrieval."""

    def __init__(
        self,
        database: Optional[MemoryDatabase] = None,
        extractor: Optional[MemoryExtractor] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.db = database or get_memory_database()
        self.extractor = extractor or MemoryExtractor()
        self.event_bus = event_bus or get_event_bus()

    def process_turn(self, user_text: str) -> Optional[MemoryItem]:
        """Analyzes a user message, extracts durable facts if present, and saves to database."""
        extracted: Optional[ExtractedMemory] = self.extractor.extract(user_text)
        if not extracted:
            return None

        # Check if identical or very similar content already exists
        existing_memories = self.db.get_all_memories(category=extracted.category)
        content_lower = extracted.content.lower().strip()
        for m in existing_memories:
            if m.content.lower().strip() == content_lower:
                logger.debug(f"Memory already recorded: '{extracted.content}'")
                return m

        # Store in SQLite database
        saved_item = self.db.add_memory(
            content=extracted.content,
            category=extracted.category,
            importance=extracted.importance,
            source_turn=user_text,
        )

        return saved_item

    def retrieve_context_for_prompt(self, query: str, max_items: int = 5) -> List[str]:
        """Finds memories relevant to the query to inject into system prompt."""
        matches: List[MemoryItem] = self.db.search_memories(query, limit=max_items)
        if not matches:
            return []

        formatted = []
        for m in matches:
            formatted.append(f"[{m.category.upper()}] {m.content}")
        return formatted

    def get_all_memories(self, category: Optional[str] = None) -> List[MemoryItem]:
        """Returns all stored memories for viewer/UI."""
        return self.db.get_all_memories(category=category)

    def update_memory(
        self,
        memory_id: int,
        content: str,
        category: Optional[str] = None,
        importance: Optional[int] = None,
    ) -> bool:
        """Edits an existing memory."""
        return self.db.update_memory(
            memory_id=memory_id,
            content=content,
            category=category,
            importance=importance,
        )

    def delete_memory(self, memory_id: int) -> bool:
        """Deletes a memory entry."""
        return self.db.delete_memory(memory_id)

    def clear_all_memories(self) -> int:
        """Wipes all local user memories."""
        return self.db.clear_all_memories()


_manager_instance: Optional[MemoryManager] = None


def get_memory_manager(db_path: Optional[Path] = None) -> MemoryManager:
    """Singleton getter for the global MemoryManager."""
    global _manager_instance
    if _manager_instance is None or db_path is not None:
        db = get_memory_database(db_path=db_path)
        _manager_instance = MemoryManager(database=db)
    return _manager_instance
