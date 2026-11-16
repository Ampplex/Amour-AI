"""
Real-Pipeline Diagnostic Test for Regenerated Variant Switching Context.

Scenario:
1. Turn 1: User asks for a codename suggestion.
2. Bot generates Response 1.
3. User regenerates -> Bot generates Response 2.
4. User regenerates -> Bot generates Response 3.
5. User regenerates -> Bot generates Response 4.
Total: 4 candidate responses for the same user turn.

6. User switches to Response 2 (variant_index = 1) using the '<' / '>' switcher (PATCH /api/memory/chat/).
7. Turn 2: User asks "What was the codename you suggested?".
8. Forensic Inspection:
   - What did PostgreSQL supply in `conversation_history`? (Response 2 or Response 4?)
   - What did Reeve supply in `memory_context`?
   - What was in the final system prompt & messages fed to the Real LLM?
   - What did the Real Bedrock LLM respond with?
"""

import os
import sys
import uuid
import time

sys.path.insert(0, os.path.abspath("backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "amour_backend.settings")

import django
django.setup()

from rest_framework.test import APIRequestFactory
from memory.views import ChatMemoryView
from memory.models import PersonaChatMessage
from memory.crypto import decrypt_chat_message
from memory.reeve_service import retrieve_context_for_user, deduplicate_context
from response_generator.generator import generate_companion_reply
from response_generator.prompt_builder import build_roleplay_system_prompt
from response_generator.llm_client import call_llm


def run_test():
    print("=" * 80)
    print("🚀 REAL PIPELINE TEST: 4x REGENERATION & SWITCHING TO 2ND VARIANT")
    print("=" * 80)

    factory = APIRequestFactory()
    view = ChatMemoryView.as_view()

    test_user_id = f"test_user_{uuid.uuid4().hex[:6]}"
    test_persona_id = f"test_persona_{uuid.uuid4().hex[:6]}"
    test_persona_name = "Elena"
    clean_user_id = test_user_id.replace(":", "_").replace("/", "_")
    clean_persona_id = test_persona_id.replace(":", "_").replace("/", "_")
    namespace = f"usr_{clean_user_id}_persona_{clean_persona_id}"

    turn1_user_msg = "Please suggest a unique one-word project codename for my new secret project."

    # -------------------------------------------------------------------------
    # STEP 1: Turn 1 (Initial Generation - Variant 1)
    # -------------------------------------------------------------------------
    print("\n[STEP 1] User sends Turn 1...")
    req1 = factory.post(
        "/api/memory/chat/",
        data={
            "message": turn1_user_msg,
            "user_id": test_user_id,
            "persona_id": test_persona_id,
            "persona_name": test_persona_name,
            "client_time": "Monday, 10:00 AM",
            "client_timezone": "UTC",
        },
        format="json",
    )
    res1 = view(req1)
    assert res1.status_code == 200, f"Step 1 failed: {res1.data}"
    bot_msg_id = res1.data["id"]
    reply_1 = res1.data["reply"]
    print(f"   🤖 Variant 1 generated: \"{reply_1}\"")

    # -------------------------------------------------------------------------
    # STEP 2: Regenerate -> Variant 2
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Regenerating (1st time) -> Variant 2...")
    req2 = factory.post(
        "/api/memory/chat/",
        data={
            "regenerate_bot_message_id": bot_msg_id,
            "message": turn1_user_msg,
            "user_id": test_user_id,
            "persona_id": test_persona_id,
            "persona_name": test_persona_name,
            "client_time": "Monday, 10:01 AM",
            "client_timezone": "UTC",
        },
        format="json",
    )
    res2 = view(req2)
    assert res2.status_code == 200, f"Step 2 failed: {res2.data}"
    reply_2 = res2.data["reply"]
    print(f"   🤖 Variant 2 generated: \"{reply_2}\"")

    # -------------------------------------------------------------------------
    # STEP 3: Regenerate -> Variant 3
    # -------------------------------------------------------------------------
    print("\n[STEP 3] Regenerating (2nd time) -> Variant 3...")
    req3 = factory.post(
        "/api/memory/chat/",
        data={
            "regenerate_bot_message_id": bot_msg_id,
            "message": turn1_user_msg,
            "user_id": test_user_id,
            "persona_id": test_persona_id,
            "persona_name": test_persona_name,
            "client_time": "Monday, 10:02 AM",
            "client_timezone": "UTC",
        },
        format="json",
    )
    res3 = view(req3)
    assert res3.status_code == 200, f"Step 3 failed: {res3.data}"
    reply_3 = res3.data["reply"]
    print(f"   🤖 Variant 3 generated: \"{reply_3}\"")

    # -------------------------------------------------------------------------
    # STEP 4: Regenerate -> Variant 4
    # -------------------------------------------------------------------------
    print("\n[STEP 4] Regenerating (3rd time) -> Variant 4 (Latest)...")
    req4 = factory.post(
        "/api/memory/chat/",
        data={
            "regenerate_bot_message_id": bot_msg_id,
            "message": turn1_user_msg,
            "user_id": test_user_id,
            "persona_id": test_persona_id,
            "persona_name": test_persona_name,
            "client_time": "Monday, 10:03 AM",
            "client_timezone": "UTC",
        },
        format="json",
    )
    res4 = view(req4)
    assert res4.status_code == 200, f"Step 4 failed: {res4.data}"
    reply_4 = res4.data["reply"]
    all_variants = res4.data.get("variants") or []
    print(f"   🤖 Variant 4 generated: \"{reply_4}\"")
    print(f"   📊 Total variants accumulated: {len(all_variants)}")
    assert len(all_variants) == 4, f"Expected 4 variants, got {len(all_variants)}"

    # -------------------------------------------------------------------------
    # STEP 5: User taps '<' to switch to Variant 2 (Index 1)
    # -------------------------------------------------------------------------
    print("\n[STEP 5] User clicks '<' to switch back to Variant 2 (Index 1)...")
    req_switch = factory.patch(
        "/api/memory/chat/",
        data={
            "message_id": bot_msg_id,
            "variant_index": 1,
            "user_id": test_user_id,
        },
        format="json",
    )
    res_switch = view(req_switch)
    assert res_switch.status_code == 200, f"Switch failed: {res_switch.data}"
    print(f"   ✅ Switched to Variant index: {res_switch.data['active_variant_index']} (Variant 2)")
    print(f"   ✅ Selected Text returned: \"{res_switch.data['text']}\"")
    assert res_switch.data["text"] == reply_2

    # Give Reeve background sync a moment to settle
    time.sleep(2)

    # -------------------------------------------------------------------------
    # STEP 6: Turn 2 - User asks follow-up question
    # -------------------------------------------------------------------------
    turn2_user_msg = "Which codename did you suggest to me? Repeat the exact name you suggested."
    print(f"\n[STEP 6] User sends Turn 2: \"{turn2_user_msg}\"")
    print("   Tracing what gets extracted from DB and supplied into the context...")

    # Query PostgreSQL conversation history (exact views.py lines 376-391)
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

    # Query Reeve memory context
    try:
        raw_mem = retrieve_context_for_user(turn2_user_msg.strip(), namespace) or ""
        memory_context = deduplicate_context(str(raw_mem))
    except Exception as exc:
        print(f"   ⚠️ Reeve retrieve notice: {exc}")
        memory_context = ""

    # Assemble system prompt & messages
    system_prompt = build_roleplay_system_prompt(
        persona_name=test_persona_name,
        persona_age=24,
        persona_tagline="Artist and Confidante",
        greeting="Hi there!",
        memory_prompt="You are Elena. You remember details accurately.",
        user_name="Alex",
        client_time="Monday, 10:05 AM",
        client_timezone="Asia/Kolkata",
        memory_context=memory_context,
        current_message=turn2_user_msg,
        has_history=bool(conversation_history),
        allow_user_name=True,
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in (conversation_history or [])[-4:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})
    messages.append({"role": "user", "content": turn2_user_msg.strip()})

    # Call Real LLM for Turn 2
    print("   🤖 Calling REAL LLM with the final assembled context...")
    turn2_reply, model_used = call_llm(
        messages=messages,
        max_tokens=256,
        temperature=0.8,
    )
    print(f"   🤖 Real LLM Response to Turn 2 ({model_used}):")
    print(f"      \"{turn2_reply}\"")

    # -------------------------------------------------------------------------
    # STEP 7: Forensic Verification Breakdown
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("🔍 FORENSIC BREAKDOWN: WHICH RESPONSE WAS PROVIDED TO CONTEXT?")
    print("=" * 80)

    bot_turn_in_history = next((t["content"] for t in conversation_history if t["role"] == "assistant"), "")

    is_variant_1_in_history = (bot_turn_in_history == reply_1)
    is_variant_2_in_history = (bot_turn_in_history == reply_2)
    is_variant_3_in_history = (bot_turn_in_history == reply_3)
    is_variant_4_in_history = (bot_turn_in_history == reply_4)

    print(f"\n1. POSTGRESQL CONVERSATION HISTORY (`conversation_history`):")
    print(f"   Total turns: {len(conversation_history)}")
    for i, t in enumerate(conversation_history):
        print(f"   Turn {i+1} [{t['role']}]: \"{t['content'][:70]}...\"")

    print(f"\n   -> Is Assistant History == Variant 1? {'YES' if is_variant_1_in_history else 'NO'}")
    print(f"   -> Is Assistant History == Variant 2 (Selected)? {'🟢 YES (CORRECT!)' if is_variant_2_in_history else 'NO'}")
    print(f"   -> Is Assistant History == Variant 3? {'YES' if is_variant_3_in_history else 'NO'}")
    print(f"   -> Is Assistant History == Variant 4 (Latest)? {'🔴 YES (WRONG!)' if is_variant_4_in_history else '🟢 NO'}")

    print(f"\n2. REEVE LONG-TERM MEMORY (`memory_context`):")
    if memory_context:
        print(f"   {memory_context}")
    else:
        print("   (Empty)")

    print(f"\n3. FINAL ASSEMBLED MESSAGES SENT TO REAL LLM:")
    for idx, m in enumerate(messages):
        if m["role"] == "system":
            print(f"   [{idx}] SYSTEM: (roleplay prompt length: {len(m['content'])} chars)")
        else:
            print(f"   [{idx}] {m['role'].upper()}: \"{m['content']}\"")

    print(f"\n4. REAL LLM OUTPUT:")
    print(f"   \"{turn2_reply}\"")

    print("\n" + "=" * 80)
    print("🎯 FINAL CONCLUSION")
    print("=" * 80)
    if is_variant_2_in_history:
        print("✅ SUCCESS: The 2nd one (the user-selected variant) is provided in context!")
        print("   PostgreSQL database row was updated to Variant 2, so the conversation history")
        print("   and LLM prompt completely ignore Variant 4 and strictly use Variant 2.")
    else:
        print("❌ FAILED: Variant 2 was NOT found in conversation history!")

    # Cleanup
    PersonaChatMessage.objects.filter(user_identifier=test_user_id).delete()
    print("\n🧹 Cleaned up test records from PostgreSQL.")
    print("=" * 80)


if __name__ == "__main__":
    run_test()
