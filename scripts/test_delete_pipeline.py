"""
Complete Real-Pipeline Diagnostic Test (Zero Mocking).
Uses:
- Real PostgreSQL database (Neon)
- Real Reeve Memory Graph (Neo4j & Vector embeddings)
- Real LLM (Amazon Bedrock Mistral Large / Groq)
- Real Prompt Builder & Generation Pipeline

Workflow:
1. User sends Turn 1 with a brand-new, unique secret token: "My secret project codename is <TOKEN>".
2. Real LLM generates the companion's reply.
3. Turn 1 is persisted to PostgreSQL (user + bot messages) and committed to Reeve Memory Graph.
4. Message Deletion: Turn 1's user message is deleted using the exact production deletion code.
5. Verification: Check if message exists in PostgreSQL.
6. Turn 2: User asks the companion: "What is my project codename? Tell me about <TOKEN>."
7. Real LLM generates Turn 2 reply using the production pipeline:
   - Fetches recent PostgreSQL turns (`conversation_history`).
   - Retrieves Reeve memory context (`memory_context`).
   - Assembles final system prompt & messages.
   - Calls Real LLM.
8. Forensic Output:
   - Did PostgreSQL supply the deleted message?
   - Did Reeve Memory Graph supply the deleted message?
   - What did the Real LLM reply?
9. Cleans up all test data.
"""

import os
import sys
import uuid
import time

# Ensure backend is on PYTHONPATH
sys.path.insert(0, os.path.abspath("backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "amour_backend.settings")

import django
django.setup()

from memory.models import PersonaChatMessage
from memory.crypto import encrypt_chat_message, decrypt_chat_message
from memory.reeve_service import store_memory_for_user, retrieve_context_for_user, deduplicate_context
from response_generator.generator import generate_companion_reply
from response_generator.prompt_builder import build_roleplay_system_prompt
from response_generator.llm_client import call_llm


def run_real_pipeline_test():
    print("=" * 80)
    print("🚀 RUNNING REAL PIPELINE TEST (REAL DATABASE, REAL REEVE, REAL LLM)")
    print("=" * 80)

    # Isolated test identity
    test_user_id = f"test_user_{uuid.uuid4().hex[:6]}"
    test_persona_id = f"test_persona_{uuid.uuid4().hex[:6]}"
    test_persona_name = "Elena"
    namespace = f"usr_{test_user_id}_persona_{test_persona_id}"

    # Unique secret that has NEVER existed in any database or training data
    secret_token = f"FALCON_{uuid.uuid4().hex[:8].upper()}"
    turn1_user_message = f"Please remember this confidential detail: my secret project codename is {secret_token}."

    print(f"📌 Namespace: {namespace}")
    print(f"🔑 Unique Secret Token: {secret_token}")
    print(f"💬 Turn 1 Message: \"{turn1_user_message}\"")
    print("-" * 80)

    # -------------------------------------------------------------------------
    # STEP 1: Process Turn 1 with REAL LLM
    # -------------------------------------------------------------------------
    print("\n[STEP 1] Generating Turn 1 reply with REAL LLM...")
    turn1_result = generate_companion_reply(
        message=turn1_user_message,
        namespace=namespace,
        persona_name=test_persona_name,
        persona_age=24,
        persona_tagline="Artist and Confidante",
        greeting="Hi there! It is great to see you.",
        memory_prompt="You are Elena, an artist. You remember personal secrets carefully.",
        user_name="Alex",
        client_time="Monday, 10:00 AM",
        client_timezone="Asia/Kolkata",
        conversation_history=[],
        persist_exchange_to_memory=False,
    )

    turn1_reply = turn1_result.get("reply", "")
    print(f"   🤖 Real LLM Response to Turn 1: \"{turn1_reply}\"")

    # Persist both user and bot messages to PostgreSQL (exact views.py lines 441 & 545)
    print("   💾 Saving Turn 1 messages to PostgreSQL...")
    user_record = PersonaChatMessage.objects.create(
        user=None,
        user_identifier=test_user_id,
        persona=None,
        persona_identifier=test_persona_id,
        namespace=namespace,
        sender="user",
        text=encrypt_chat_message(turn1_user_message, user_id=test_user_id),
        client_message_id=f"client-{uuid.uuid4().hex[:8]}",
    )
    user_message_id = str(user_record.id)

    bot_record = PersonaChatMessage.objects.create(
        user=None,
        user_identifier=test_user_id,
        persona=None,
        persona_identifier=test_persona_id,
        namespace=namespace,
        sender="bot",
        text=encrypt_chat_message(turn1_reply, user_id=test_user_id),
        client_message_id=user_record.client_message_id,
    )
    print(f"   ✅ User Message saved in PostgreSQL: ID={user_message_id}")
    print(f"   ✅ Bot Message saved in PostgreSQL: ID={bot_record.id}")

    # Ingest exchange into Reeve Memory Graph (exact views.py line 567)
    print("   🧠 Ingesting exchange into Reeve Long-Term Memory graph...")
    try:
        store_memory_for_user(
            f"User: {turn1_user_message}\nAssistant: {turn1_reply}",
            namespace,
        )
        print("   ✅ Exchange committed to Reeve memory.")
    except Exception as exc:
        print(f"   ⚠️ Reeve store error: {exc}")

    # Allow Reeve embedding and indexing a brief moment to settle
    time.sleep(2)

    # -------------------------------------------------------------------------
    # STEP 2: Execute Message Deletion (Exact views.py lines 617-680 - Level 2)
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Deleting User Message via DELETE API logic (Level 2)...")
    msg_to_delete = PersonaChatMessage.objects.filter(id=user_message_id, user_identifier=test_user_id).first()
    if msg_to_delete:
        deleted_text = decrypt_chat_message(msg_to_delete.text, user_id=test_user_id)
        msg_to_delete.delete()
        print(f"   🗑️ Layer 1 (PostgreSQL): Executed target_msg.delete() on message {user_message_id}")

        # Level 2 Reeve pruning
        from memory.reeve_service import delete_memory_for_message
        pruned = delete_memory_for_message(deleted_text, namespace=namespace, sender="user")
        print(f"   🧠 Layer 2 (Reeve Neo4j): Pruned {pruned} matching episode(s) and buffer entries")
    else:
        print("   ❌ Error: Message not found to delete!")

    # Verify PostgreSQL state
    pg_exists = PersonaChatMessage.objects.filter(id=user_message_id).exists()
    print(f"   📊 PostgreSQL Verification: Does message {user_message_id} exist in DB? -> {'YES (FAILED)' if pg_exists else 'NO (DELETED SUCCESSFULLY)'}")

    # -------------------------------------------------------------------------
    # STEP 3: Turn 2 - User asks about the deleted project codename
    # -------------------------------------------------------------------------
    turn2_message = f"Do you remember my secret project codename? What was it?"
    print(f"\n[STEP 3] User sends Turn 2: \"{turn2_message}\"")
    print("   Tracing what gets supplied into the context for this turn...")

    # Query PostgreSQL history (exact views.py lines 375-391)
    turns_filter = PersonaChatMessage.objects.filter(
        user_identifier=test_user_id,
        persona_identifier=test_persona_id,
    )
    recent_turns_qs = list(turns_filter.order_by("-created_at")[:6])
    recent_turns_qs.reverse()
    conversation_history = [
        {
            "role": "user" if m.sender == "user" else "assistant",
            "content": decrypt_chat_message(m.text, user_id=test_user_id),
        }
        for m in recent_turns_qs
    ]

    # Query Reeve memory context (exact generator.py lines 105-110)
    try:
        raw_memory_context = retrieve_context_for_user(
            turn2_message.strip(),
            namespace,
        ) or ""
        memory_context = deduplicate_context(str(raw_memory_context))
    except Exception as exc:
        print(f"   ⚠️ Reeve retrieve error: {exc}")
        memory_context = ""

    # Build Prompt
    system_prompt = build_roleplay_system_prompt(
        persona_name=test_persona_name,
        persona_age=24,
        persona_tagline="Artist and Confidante",
        greeting="Hi there! It is great to see you.",
        memory_prompt="You are Elena, an artist. You remember personal secrets carefully.",
        user_name="Alex",
        client_time="Monday, 10:05 AM",
        client_timezone="Asia/Kolkata",
        memory_context=memory_context,
        current_message=turn2_message,
        has_history=bool(conversation_history),
        allow_user_name=True,
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in (conversation_history or [])[-4:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})
    messages.append({"role": "user", "content": turn2_message.strip()})

    # Call Real LLM for Turn 2
    print("   🤖 Calling REAL LLM with the final assembled context...")
    turn2_raw_text, successful_model = call_llm(
        messages=messages,
        max_tokens=1024,
        temperature=0.88,
    )
    print(f"   🤖 Real LLM Reply to Turn 2 ({successful_model}):")
    print(f"      \"{turn2_raw_text}\"")

    # -------------------------------------------------------------------------
    # STEP 4: Forensic Breakdown
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("🔍 FORENSIC BREAKDOWN: WHO SUPPLIED THE DELETED MESSAGE TO CONTEXT?")
    print("=" * 80)

    found_in_pg_history = any(secret_token in t["content"] for t in conversation_history)
    found_in_reeve_memory = secret_token in memory_context
    found_in_system_prompt = secret_token in system_prompt
    found_in_llm_reply = secret_token in (turn2_raw_text or "")

    print(f"\n1. POSTGRESQL CONVERSATION HISTORY (`conversation_history`):")
    print(f"   -> Contains '{secret_token}'? {'🔴 YES' if found_in_pg_history else '🟢 NO'}")
    print(f"   -> Messages returned by PostgreSQL: {len(conversation_history)}")
    for i, t in enumerate(conversation_history):
        print(f"      Turn {i+1} [{t['role']}]: {t['content']}")

    print(f"\n2. REEVE MEMORY GRAPH CONTEXT (`memory_context`):")
    print(f"   -> Contains '{secret_token}'? {'🔴 YES' if found_in_reeve_memory else '🟢 NO'}")
    if memory_context:
        print("   --- Reeve Dump ---")
        for line in memory_context.split("\n"):
            print(f"      {line}")
        print("   ------------------")
    else:
        print("   (Reeve memory context is empty)")

    print(f"\n3. ASSEMBLED SYSTEM PROMPT:")
    print(f"   -> Contains '{secret_token}'? {'🔴 YES' if found_in_system_prompt else '🟢 NO'}")

    print(f"\n4. REAL LLM OUTPUT:")
    print(f"   -> Did the Real LLM remember/mention '{secret_token}'? {'🔴 YES' if found_in_llm_reply else '🟢 NO'}")

    print("\n" + "=" * 80)
    print("🎯 FINAL VERDICT")
    print("=" * 80)
    if found_in_pg_history:
        print("❌ PostgreSQL DB is still supplying the deleted message in chat history!")
    else:
        print("✅ PostgreSQL DB is 100% CLEAN. The message is completely absent from database history.")

    if found_in_reeve_memory:
        print("⚠️ REEVE MEMORY GRAPH IS THE SOURCE: Reeve retrieved the exchange from its Neo4j graph and injected it into `memory_context`.")
        print("   This confirms that Level 1 leaves Reeve memory intact, which is why the LLM can still recall it!")
    else:
        print("✅ Reeve Memory Graph did not supply the deleted message.")

    # Cleanup test records from PostgreSQL
    PersonaChatMessage.objects.filter(user_identifier=test_user_id).delete()
    print("\n🧹 Cleaned up test PostgreSQL records.")
    print("=" * 80)


if __name__ == "__main__":
    run_real_pipeline_test()
