"""
Unit and integration tests for JARVIS Persistent Memory System.
"""

from pathlib import Path
import pytest

from app.memory.database import MemoryDatabase, MemoryItem
from app.memory.extractor import MemoryExtractor, ExtractedMemory
from app.memory.manager import MemoryManager
from app.core.conversation import ConversationManager
from app.ai.base import AIProvider, AIResponse, TokenUsage


class MemoryRecordingProvider(AIProvider):
    def __init__(self):
        super().__init__(model_name="mem-rec-v1")
        self.last_system_prompt = ""

    @property
    def provider_name(self) -> str:
        return "mem_recorder"

    def generate(self, messages, system_prompt=None, **kwargs):
        self.last_system_prompt = system_prompt or ""
        return AIResponse(
            content="Answer received",
            model="mem-rec-v1",
            usage=TokenUsage(5, 5, 10),
            latency_ms=10.0,
        )

    def stream(self, *args, **kwargs):
        yield "mem"

    def health_check(self):
        return True, "MemRecorder OK"


@pytest.fixture
def temp_db(tmp_path: Path):
    """Provides an isolated SQLite memory database for each test."""
    db_file = tmp_path / "test_memory.db"
    return MemoryDatabase(db_path=db_file)


def test_database_crud_operations(temp_db: MemoryDatabase):
    # 1. Add
    item = temp_db.add_memory(
        content="User loves black coffee",
        category="preference",
        importance=4,
    )
    assert item.id is not None
    assert item.content == "User loves black coffee"
    assert item.category == "preference"
    assert item.importance == 4

    # 2. Get
    retrieved = temp_db.get_memory(item.id)
    assert retrieved is not None
    assert retrieved.id == item.id
    assert retrieved.content == item.content

    # 3. Update
    updated = temp_db.update_memory(item.id, content="User prefers espresso with no sugar", importance=5)
    assert updated is True
    retrieved_after_update = temp_db.get_memory(item.id)
    assert retrieved_after_update.content == "User prefers espresso with no sugar"
    assert retrieved_after_update.importance == 5

    # 4. List all
    all_mems = temp_db.get_all_memories()
    assert len(all_mems) == 1

    # 5. Delete
    deleted = temp_db.delete_memory(item.id)
    assert deleted is True
    assert temp_db.get_memory(item.id) is None
    assert len(temp_db.get_all_memories()) == 0


def test_database_keyword_search(temp_db: MemoryDatabase):
    temp_db.add_memory("User favorite framework is PyQt6", category="preference", importance=5)
    temp_db.add_memory("User works at DeepMind as an engineer", category="user_fact", importance=4)
    temp_db.add_memory("User is building a desktop AI assistant named Jarvis", category="project", importance=5)

    # Search for "PyQt"
    results = temp_db.search_memories("Tell me about PyQt GUI development")
    assert len(results) > 0
    assert "PyQt6" in results[0].content

    # Search for "assistant project"
    proj_results = temp_db.search_memories("What is the status of my assistant project?")
    assert len(proj_results) > 0
    assert "Jarvis" in proj_results[0].content


def test_memory_extractor_transient_filtering():
    extractor = MemoryExtractor()

    # Ephemeral / Transient queries MUST NOT produce memories
    assert extractor.extract("What time is it?") is None
    assert extractor.extract("Kitne baje hain?") is None
    assert extractor.extract("What is the weather in Delhi?") is None
    assert extractor.extract("Who is the prime minister of India?") is None
    assert extractor.extract("Open Google Chrome please") is None
    assert extractor.extract("Hello Jarvis, how are you doing?") is None
    assert extractor.extract("Thank you very much") is None
    assert extractor.extract("Theek hai") is None


def test_memory_extractor_durable_facts():
    extractor = MemoryExtractor()

    # Explicit instruction
    mem1 = extractor.extract("Remember that my favorite programming language is Python.")
    assert mem1 is not None
    assert "Python" in mem1.content
    assert mem1.importance >= 4

    # Hindi identity
    mem2 = extractor.extract("Mera naam Rohan hai")
    assert mem2 is not None
    assert "Rohan" in mem2.content
    assert mem2.category == "user_fact"

    # Project
    mem3 = extractor.extract("I am working on an autonomous drone system")
    assert mem3 is not None
    assert mem3.category == "project"

    # Preference
    mem4 = extractor.extract("I prefer dark mode in all editors")
    assert mem4 is not None
    assert mem4.category == "preference"


def test_memory_manager_persistence_and_privacy(temp_db: MemoryDatabase):
    manager = MemoryManager(database=temp_db)

    # Process turns
    item1 = manager.process_turn("Remember that my favorite programming language is Python")
    assert item1 is not None

    # Deduplication test: identical turn should not insert a duplicate
    item1_dup = manager.process_turn("Remember that my favorite programming language is Python")
    assert item1_dup is not None
    assert item1_dup.id == item1.id
    assert len(manager.get_all_memories()) == 1

    # Transient turn produces no memory
    assert manager.process_turn("What time is it now?") is None
    assert len(manager.get_all_memories()) == 1

    # Context retrieval for prompt
    context_lines = manager.retrieve_context_for_prompt("What language do you recommend?")
    assert len(context_lines) > 0
    assert any("Python" in line for line in context_lines)

    # Privacy Wipe
    purged_count = manager.clear_all_memories()
    assert purged_count == 1
    assert len(manager.get_all_memories()) == 0


def test_conversation_manager_memory_injection(temp_db: MemoryDatabase):
    rec_provider = MemoryRecordingProvider()
    manager = MemoryManager(database=temp_db)

    conv = ConversationManager(
        provider=rec_provider,
        memory_manager=manager,
    )

    # 1. User shares a durable fact
    conv.send_user_message("Remember that my favorite programming language is Python")

    # Verify fact was persisted
    mems = manager.get_all_memories()
    assert len(mems) == 1
    assert "Python" in mems[0].content

    # 2. Next turn asks a relevant question
    conv.send_user_message("Which programming language should I write my script in?")

    # Verify that PromptBuilder injected the retrieved memory into the system prompt!
    assert "RELEVANT USER MEMORIES & PREFERENCES:" in rec_provider.last_system_prompt
    assert "Python" in rec_provider.last_system_prompt
