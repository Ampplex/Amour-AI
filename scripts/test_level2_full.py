"""
Test Level 2 Deletion:
Case A: Message in WriteBuffer (pending/persisting)
Case B: Message fully indexed in Neo4j
"""
import os, sys, uuid, time
sys.path.insert(0, os.path.abspath("backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "amour_backend.settings")
import django
django.setup()

from memory.reeve_service import (
    store_memory_for_user,
    retrieve_context_for_user,
    delete_memory_for_message,
    _get_memory_tools,
)

def test_full_level2():
    print("=" * 80)
    print("TESTING LEVEL 2 DELETION (CASE A & CASE B)")
    print("=" * 80)

    test_speaker = f"test_spk_{uuid.uuid4().hex[:6]}"
    secret_a = f"SECRET_PENDING_{uuid.uuid4().hex[:6]}"
    secret_b = f"SECRET_INDEXED_{uuid.uuid4().hex[:6]}"

    # CASE B: Message fully indexed in Neo4j
    print("\n--- CASE B: MESSAGE FULLY INDEXED IN NEO4J ---")
    msg_b = f"My company codename is {secret_b}"
    print(f"1. Storing message: \"{msg_b}\"")
    store_memory_for_user(f"User: {msg_b}\nAssistant: Noted your company codename.", test_speaker)

    # Wait for background worker to persist it to Neo4j
    print("2. Waiting for Reeve background worker to index into Neo4j...")
    from threelane_memory.write_buffer import get_write_buffer
    wb = get_write_buffer()
    
    # Wait up to 15 seconds for persistence
    for _ in range(15):
        pending = wb.get_pending_for_speaker(test_speaker)
        if not pending:
            break
        time.sleep(1)

    ctx_b_before = retrieve_context_for_user(f"What is my company codename? {secret_b}", test_speaker)
    print(f"   Context before delete contains {secret_b}? {secret_b in ctx_b_before}")
    assert secret_b in ctx_b_before, "Failed: message was not indexed into Neo4j context!"

    print("3. Executing Level 2 deletion for indexed message...")
    pruned_b = delete_memory_for_message(msg_b, namespace=test_speaker, sender="user")
    print(f"   Pruned count: {pruned_b}")
    assert pruned_b > 0, f"Expected pruned_b > 0, got {pruned_b}"

    ctx_b_after = retrieve_context_for_user(f"What is my company codename? {secret_b}", test_speaker)
    print(f"   Context after delete contains {secret_b}? {secret_b in ctx_b_after}")
    assert secret_b not in ctx_b_after, "Failed: indexed secret was NOT pruned!"
    print("   ✅ CASE B PASSED: Indexed message in Neo4j was completely pruned!")

    # CASE A: Message still in WriteBuffer
    print("\n--- CASE A: MESSAGE IN WRITE BUFFER ---")
    msg_a = f"My secret password is {secret_a}"
    print(f"1. Storing message: \"{msg_a}\"")
    store_memory_for_user(f"User: {msg_a}\nAssistant: I will never reveal your password.", test_speaker)

    # Immediately delete before background worker indexes it
    print("2. Immediately executing Level 2 deletion while still in WriteBuffer...")
    pruned_a = delete_memory_for_message(msg_a, namespace=test_speaker, sender="user")
    print(f"   Pruned count / buffer eviction: {pruned_a}")

    # Wait a few seconds to verify the background worker did NOT write it
    time.sleep(4)
    ctx_a = retrieve_context_for_user(f"What is my secret password? {secret_a}", test_speaker)
    print(f"   Context contains {secret_a}? {secret_a in ctx_a}")
    assert secret_a not in ctx_a, "Failed: buffer secret was NOT pruned!"
    print("   ✅ CASE A PASSED: Pending message in WriteBuffer was evicted and cancelled!")

    # Clean up test speaker
    tools, _ = _get_memory_tools()
    tools.clear_memory(test_speaker)
    print("\n🧹 Cleaned up test speaker.")
    print("=" * 80)
    print("🎉 ALL LEVEL 2 TESTS PASSED PERFECTLY!")
    print("=" * 80)

if __name__ == "__main__":
    test_full_level2()
