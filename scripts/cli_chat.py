"""
CLI Chat Test Harness for JARVIS (Phase 1).
Allows testing natural language conversation, provider switching, and telemetry in the terminal.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output in Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import get_settings
from app.core.conversation import ConversationManager
from app.core.events import Event, EventType, get_event_bus
from app.ai.factory import create_ai_provider


def main():
    settings = get_settings()
    bus = get_event_bus()

    print("=" * 60)
    print("      J.A.R.V.I.S. - CLI TEST HARNESS (PHASE 1)")
    print("=" * 60)
    print(f"Active Provider: {settings.ai_provider}")
    print(f"Gemini Key:      {settings.mask_key(settings.gemini_api_key)}")
    print(f"OpenAI Key:      {settings.mask_key(settings.openai_api_key)}")
    print(f"Local Endpoint:  {settings.local_api_base_url}")
    print("-" * 60)
    print("Commands:")
    print("  /provider <gemini|openai|local>  - Switch active provider")
    print("  /clear                           - Clear conversation history")
    print("  /health                          - Health check active provider")
    print("  /memories                        - View all stored long-term memories")
    print("  /remember <text>                 - Manually store a memory fact")
    print("  /forget                          - Wipe all local memories (privacy)")
    print("  /emotion                         - View simulated emotional state vector")
    print("  /exit                            - Quit CLI")
    print("=" * 60)

    manager = ConversationManager()

    # Listen to event bus for telemetry display
    def on_thinking(evt: Event):
        provider = evt.data.get("provider", "unknown")
        intent = evt.data.get("intent", "query")
        lang = evt.data.get("language", "en")
        user_emo = "neutral"
        dom = "calm"
        if manager.emotion_engine:
            ctx = manager.emotion_engine.get_context_for_prompt()
            user_emo = ctx.get("user_emotion", "neutral")
            dom = ctx.get("dominant_emotion", "calm")
        print(f"\n[JARVIS is thinking... ({provider} | Intent: {intent} | Lang: {lang} | User: {user_emo} | Posture: {dom})]")

    bus.subscribe(EventType.JARVIS_THINKING_START, on_thinking)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("/exit", "exit", "quit"):
                print("Exiting JARVIS CLI. Good day.")
                break

            if user_input.lower() == "/clear":
                manager.clear_history()
                print("[Conversation history cleared]")
                continue

            if user_input.lower() == "/health":
                healthy, status_str = manager.provider.health_check()
                status_icon = "[OK]" if healthy else "[FAIL]"
                print(f"{status_icon} Provider '{manager.provider.provider_name}': {status_str}")
                continue

            if user_input.lower() == "/memories":
                if manager.memory_manager:
                    mems = manager.memory_manager.get_all_memories()
                    if not mems:
                        print("[No long-term memories stored yet]")
                    else:
                        print(f"\n[Stored Long-Term Memories ({len(mems)})]:")
                        for m in mems:
                            print(f"  #{m.id} [{m.category.upper()}] (Importance: {m.importance}) - {m.content}")
                else:
                    print("[Memory manager not active]")
                continue

            if user_input.lower() == "/forget":
                if manager.memory_manager:
                    count = manager.memory_manager.clear_all_memories()
                    print(f"[Privacy Wipe: {count} memories deleted from database]")
                continue

            if user_input.startswith("/remember"):
                text_to_save = user_input[len("/remember"):].strip()
                if text_to_save and manager.memory_manager:
                    saved = manager.memory_manager.db.add_memory(content=text_to_save, category="user_fact", importance=5)
                    print(f"[Memory #{saved.id} stored: '{saved.content}']")
                continue

            if user_input.lower() == "/emotion":
                if manager.emotion_engine:
                    state = manager.emotion_engine.state
                    det = manager.emotion_engine.last_detected_user_emotion
                    det_str = f"{det.emotion.value} (Confidence: {det.confidence:.2f})" if det else "None"
                    print("\n[JARVIS Simulated Emotional State]:")
                    for k, v in state.to_dict().items():
                        print(f"  {k.capitalize():<12}: {v}/100")
                    print(f"  Dominant Posture: {state.dominant_emotion()}")
                    print(f"  Last User Emotion: {det_str}")
                continue

            if user_input.startswith("/provider"):
                parts = user_input.split()
                if len(parts) > 1:
                    target_prov = parts[1].lower()
                    try:
                        new_provider = create_ai_provider(provider_name=target_prov, settings=settings)
                        manager.set_provider(new_provider)
                        print(f"[Switched provider to: {target_prov}]")
                    except Exception as e:
                        print(f"[Failed to switch provider: {e}]")
                else:
                    print(f"Current provider: {manager.provider.provider_name}")
                continue

            response = manager.send_user_message(user_input)

            print(f"\nJARVIS: {response.content}")
            print(f"[Latency: {response.latency_ms:.1f}ms | Tokens: {response.usage.total_tokens}]")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting JARVIS CLI. Good day.")
            break
        except Exception as e:
            print(f"\n[Unexpected Error: {e}]")


if __name__ == "__main__":
    main()
