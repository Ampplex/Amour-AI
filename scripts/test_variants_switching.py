"""
Automated Test for Bot Message Regeneration & Variant Switching (PostgreSQL & API).
Verifies:
1. Message creation sets active_variant_index=0 and variants=[reply_1].
2. Regeneration via POST appends variant 2 and updates PostgreSQL text column to reply_2.
3. PATCH /api/memory/chat/ updates PostgreSQL text column to reply_1 when switching to variant 0.
4. GET /api/memory/chat/ returns decrypted variants and active_variant_index.
5. PATCH /api/memory/chat/ updates PostgreSQL text column to reply_2 when switching back to variant 1.
"""

import os
import sys
import uuid
import json

sys.path.insert(0, os.path.abspath("backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "amour_backend.settings")

import django
django.setup()

from rest_framework.test import APIRequestFactory
from memory.views import ChatMemoryView
from memory.models import PersonaChatMessage
from memory.crypto import decrypt_chat_message

def test_variants_flow():
    print("=" * 80)
    print("TESTING REGENERATED MESSAGE VARIANT SWITCHING & POSTGRESQL UPDATES")
    print("=" * 80)

    factory = APIRequestFactory()
    view = ChatMemoryView.as_view()

    test_user_id = f"test_user_{uuid.uuid4().hex[:6]}"
    test_persona_id = f"test_persona_{uuid.uuid4().hex[:6]}"

    # --- STEP 1: Turn 1 (Initial Generation) ---
    print("\n[STEP 1] Sending Turn 1...")
    req1 = factory.post(
        "/api/memory/chat/",
        data={
            "message": "Hello, how are you?",
            "user_id": test_user_id,
            "persona_id": test_persona_id,
            "persona_name": "Elena",
            "client_time": "Monday, 10:00 AM",
            "client_timezone": "UTC",
        },
        format="json",
    )
    res1 = view(req1)
    assert res1.status_code == 200, f"Step 1 failed with {res1.status_code}: {res1.data}"
    bot_msg_id = res1.data["id"]
    reply_1 = res1.data["reply"]
    variants_1 = res1.data.get("variants") or []
    active_idx_1 = res1.data.get("active_variant_index", 0)

    print(f"   ✅ Initial Bot Reply generated (ID={bot_msg_id}): \"{reply_1[:50]}...\"")
    print(f"   Variants count: {len(variants_1)}, Active index: {active_idx_1}")
    assert len(variants_1) == 1, f"Expected 1 variant initially, got {len(variants_1)}"
    assert active_idx_1 == 0, f"Expected active index 0, got {active_idx_1}"

    # Verify PostgreSQL
    pg_msg_1 = PersonaChatMessage.objects.get(id=bot_msg_id)
    decrypted_pg_text_1 = decrypt_chat_message(pg_msg_1.text, user_id=test_user_id)
    assert decrypted_pg_text_1 == reply_1, "PostgreSQL text does not match reply_1"
    print(f"   ✅ PostgreSQL verification: row text matches reply_1")

    # --- STEP 2: Regenerate Bot Reply ---
    print("\n[STEP 2] Regenerating Bot Reply for the same message...")
    req2 = factory.post(
        "/api/memory/chat/",
        data={
            "regenerate_bot_message_id": bot_msg_id,
            "message": "Hello, how are you?",
            "user_id": test_user_id,
            "persona_id": test_persona_id,
            "persona_name": "Elena",
            "client_time": "Monday, 10:02 AM",
            "client_timezone": "UTC",
        },
        format="json",
    )
    res2 = view(req2)
    assert res2.status_code == 200, f"Step 2 failed with {res2.status_code}: {res2.data}"
    reply_2 = res2.data["reply"]
    variants_2 = res2.data.get("variants") or []
    active_idx_2 = res2.data.get("active_variant_index")

    print(f"   ✅ Regenerated Reply: \"{reply_2[:50]}...\"")
    print(f"   Variants count: {len(variants_2)}, Active index: {active_idx_2}")
    assert len(variants_2) == 2, f"Expected 2 variants after regeneration, got {len(variants_2)}"
    assert active_idx_2 == 1, f"Expected active index 1, got {active_idx_2}"
    assert variants_2[0] == reply_1, "Variant 0 should be original reply"
    assert variants_2[1] == reply_2, "Variant 1 should be newly regenerated reply"

    # Verify PostgreSQL row updated to reply_2
    pg_msg_2 = PersonaChatMessage.objects.get(id=bot_msg_id)
    decrypted_pg_text_2 = decrypt_chat_message(pg_msg_2.text, user_id=test_user_id)
    assert decrypted_pg_text_2 == reply_2, "PostgreSQL text does not match newly regenerated reply_2"
    assert pg_msg_2.response_metadata.get("active_variant_index") == 1
    print(f"   ✅ PostgreSQL verification: row text updated to reply_2, active_variant_index=1")

    # --- STEP 3: Switch to Previous Variant (Index 0) via PATCH ---
    print("\n[STEP 3] User taps '<' to switch back to Variant 0 (previous response)...")
    req3 = factory.patch(
        "/api/memory/chat/",
        data={
            "message_id": bot_msg_id,
            "variant_index": 0,
            "user_id": test_user_id,
        },
        format="json",
    )
    res3 = view(req3)
    assert res3.status_code == 200, f"Step 3 failed with {res3.status_code}: {res3.data}"
    assert res3.data["active_variant_index"] == 0
    assert res3.data["text"] == reply_1

    # Verify PostgreSQL row text was updated to reply_1
    pg_msg_3 = PersonaChatMessage.objects.get(id=bot_msg_id)
    decrypted_pg_text_3 = decrypt_chat_message(pg_msg_3.text, user_id=test_user_id)
    assert decrypted_pg_text_3 == reply_1, f"PostgreSQL text was NOT updated to reply_1! Got: {decrypted_pg_text_3[:50]}"
    assert pg_msg_3.response_metadata.get("active_variant_index") == 0
    print(f"   ✅ PostgreSQL verification: row text updated to reply_1, active_variant_index=0")

    # --- STEP 4: Fetch Chat History via GET ---
    print("\n[STEP 4] Fetching chat history via GET to verify decrypted variants & active selection...")
    req4 = factory.get(
        f"/api/memory/chat/?persona_id={test_persona_id}&user_id={test_user_id}",
    )
    res4 = view(req4)
    assert res4.status_code == 200, f"Step 4 failed with {res4.status_code}: {res4.data}"
    results = res4.data.get("results", [])
    bot_in_history = next((m for m in results if m["id"] == bot_msg_id), None)
    assert bot_in_history is not None, "Bot message not found in history"
    assert bot_in_history["text"] == reply_1, "Active text in history should be reply_1"
    assert bot_in_history.get("variants") == [reply_1, reply_2], "History does not contain both variants"
    assert bot_in_history.get("active_variant_index") == 0, "History active_variant_index should be 0"
    print(f"   ✅ Chat history verification: returns both variants and active_variant_index=0")

    # --- STEP 5: Switch Forward to Variant 1 via PATCH ---
    print("\n[STEP 5] User taps '>' to switch forward to Variant 1 (latest response)...")
    req5 = factory.patch(
        "/api/memory/chat/",
        data={
            "message_id": bot_msg_id,
            "variant_index": 1,
            "user_id": test_user_id,
        },
        format="json",
    )
    res5 = view(req5)
    assert res5.status_code == 200, f"Step 5 failed with {res5.status_code}: {res5.data}"
    assert res5.data["active_variant_index"] == 1
    assert res5.data["text"] == reply_2

    # Verify PostgreSQL row text was updated back to reply_2
    pg_msg_5 = PersonaChatMessage.objects.get(id=bot_msg_id)
    decrypted_pg_text_5 = decrypt_chat_message(pg_msg_5.text, user_id=test_user_id)
    assert decrypted_pg_text_5 == reply_2, f"PostgreSQL text was NOT updated to reply_2! Got: {decrypted_pg_text_5[:50]}"
    assert pg_msg_5.response_metadata.get("active_variant_index") == 1
    print(f"   ✅ PostgreSQL verification: row text updated back to reply_2, active_variant_index=1")

    # Cleanup test records
    PersonaChatMessage.objects.filter(user_identifier=test_user_id).delete()
    print("\n🧹 Cleaned up test records from PostgreSQL.")
    print("=" * 80)
    print("🎉 ALL VARIANT SWITCHING & POSTGRESQL UPDATE TESTS PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    test_variants_flow()
