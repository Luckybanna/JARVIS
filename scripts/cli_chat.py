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
    print("  /exit                            - Quit CLI")
    print("=" * 60)

    # Listen to event bus for telemetry display
    def on_thinking(evt: Event):
        print(f"\n[JARVIS is thinking... ({evt.data.get('provider')})]")

    bus.subscribe(EventType.JARVIS_THINKING_START, on_thinking)

    manager = ConversationManager()

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
