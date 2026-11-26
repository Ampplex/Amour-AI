import logging
import time
from django.db import transaction
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .crypto import (
    encrypt_chat_message,
    decrypt_chat_message,
    migrate_user_messages_to_client_key,
)
from .reeve_service import (
    get_reeve_status,
    store_memory_for_user,
    query_memory_for_user,
    retrieve_context_for_user,
    clear_user_memories,
)
from response_generator import (
    generate_companion_reply,
    strip_emojis,
)

logger = logging.getLogger(__name__)

class ReeveStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        status_data = get_reeve_status()
        return Response(status_data)

@method_decorator(sensitive_post_parameters("user_key", "client_key"), name="dispatch")
@method_decorator(sensitive_variables("user_key", "client_key", "message", "reply_text"), name="post")
class ChatMemoryView(APIView):
    """
    Companion roleplay chat endpoint powered 100% by Reeve memory graph and Groq LLM.
    Strictly ZERO emojis, short WhatsApp-style humanized replies, dynamic first message opening script,
    and temporal date/time anchor.
    Fully isolates Reeve memory namespaces per (user_id, persona_id) and persists chat logs in PostgreSQL.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Retrieve paginated chat history for a specific (user_id, persona_id) conversation.
        """
        persona_id = request.query_params.get("persona_id", "").strip()
        user_id = (request.user.id if request.user.is_authenticated else request.query_params.get("user_id", "")).strip()
        user_key = (request.headers.get("X-Memory-User-Key") or request.query_params.get("user_key") or "").strip() or None

        if not persona_id or not user_id:
            return Response(
                {"results": [], "count": 0, "page": 1, "has_more": False},
                status=status.HTTP_200_OK,
            )

        # Automatic Client-Key Handover: Migrate any legacy or server-encrypted messages
        # to the client's Zero-Knowledge key on first authenticated contact
        if user_key:
            try:
                migrate_user_messages_to_client_key(user_id, user_key)
            except Exception as exc:
                logger.warning("Error during client-key handover: %s", type(exc).__name__)

        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            page = 1
        try:
            page_size = min(100, max(1, int(request.query_params.get("page_size", 30))))
        except ValueError:
            page_size = 30

        from .models import PersonaChatMessage
        from .serializers import PersonaChatMessageSerializer

        qs = PersonaChatMessage.objects.filter(
            persona_identifier=persona_id,
            user_identifier=user_id,
        ).order_by("-created_at")

        total_count = qs.count()

        # Ingest persona memory into Reeve when user opens the chat for the first time
        if total_count == 0:
            from .models import Persona
            persona_obj = Persona.objects.filter(id=persona_id).first()
            clean_user_id = str(user_id).strip().replace(":", "_").replace("/", "_")
            clean_persona_id = str(persona_id).strip().replace(":", "_").replace("/", "_")
            namespace = f"usr_{clean_user_id}_persona_{clean_persona_id}"

            if persona_obj:
                # 1. Immediately create opening greeting in PostgreSQL (takes ~3ms)
                # Client receives the response instantly without waiting for Reeve
                if persona_obj.greeting and persona_obj.greeting.strip():
                    try:
                        user_obj = request.user if request.user.is_authenticated else None
                        if not user_obj and user_id and user_id != "guest":
                            try:
                                from authentication.models import User
                                user_obj = User.objects.filter(id=user_id).first()
                            except Exception:
                                pass

                        first_bot_msg = PersonaChatMessage.objects.create(
                            user=user_obj,
                            user_identifier=user_id,
                            persona=persona_obj,
                            persona_identifier=persona_id,
                            namespace=namespace,
                            sender="bot",
                            text=encrypt_chat_message(persona_obj.greeting.strip(), user_id=str(user_id), client_key=user_key),
                        )

                        qs = PersonaChatMessage.objects.filter(
                            persona_identifier=persona_id,
                            user_identifier=user_id,
                        ).order_by("-created_at")
                        total_count = 1
                    except Exception as exc:
                        logger.warning(f"Could not persist initial greeting: {exc}")

                # 2. Ingest persona core memory + greeting into Reeve memory graph
                # Processed non-blockingly via Reeve's native PersistWorker & WriteAhead buffer (ASYNC_WRITE_ENABLED=true)
                if persona_obj.memory_prompt and persona_obj.memory_prompt.strip():
                    try:
                        from .reeve_service import store_memory_for_user
                        store_memory_for_user(
                            f"Core Story & Mind of {persona_obj.name}:\n{persona_obj.memory_prompt.strip()}",
                            namespace,
                            user_key=user_key,
                        )
                    except Exception as exc:
                        logger.warning(f"Could not ingest initial persona memory into Reeve: {exc}")

                if persona_obj.greeting and persona_obj.greeting.strip():
                    try:
                        from .reeve_service import store_memory_for_user
                        store_memory_for_user(
                            f"Assistant: {persona_obj.greeting.strip()}",
                            namespace,
                            user_key=user_key,
                        )
                    except Exception:
                        pass

        start = (page - 1) * page_size
        end = start + page_size
        paged_items = list(qs[start:end])
        paged_items.reverse()

        serializer = PersonaChatMessageSerializer(paged_items, many=True)
        decrypted_results = []
        for item in serializer.data:
            item_copy = dict(item)
            item_copy["text"] = decrypt_chat_message(item_copy.get("text", ""), user_id=str(user_id), client_key=user_key)
            resp_meta = item_copy.get("response_metadata") or {}
            raw_variants = resp_meta.get("variants") or []
            if raw_variants and len(raw_variants) > 1:
                item_copy["variants"] = [
                    decrypt_chat_message(v, user_id=str(user_id), client_key=user_key)
                    for v in raw_variants
                ]
                item_copy["active_variant_index"] = resp_meta.get("active_variant_index", len(raw_variants) - 1)
            decrypted_results.append(item_copy)

        from .models import PersonaRelationshipState
        rel_state = PersonaRelationshipState.objects.filter(
            user_identifier=user_id,
            persona_identifier=persona_id,
        ).first()
        current_conflict_stage = rel_state.conflict_stage if rel_state else 0
        current_story_tone = (getattr(rel_state, "story_tone", "default") if rel_state else "default") or "default"

        return Response(
            {
                "results": decrypted_results,
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "has_more": end < total_count,
                "conflict_stage": current_conflict_stage,
                "conflict_level": current_conflict_stage,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        is_autonomous_continue = bool(
            request.data.get("is_autonomous_continue")
            or request.data.get("trigger_continue")
            or not message
        )
        persona_id = (request.data.get("persona_id") or "").strip()
        persona_name = (request.data.get("persona_name") or "").strip()

        if not message and not is_autonomous_continue:
            return Response(
                {"error": "Message content cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not persona_id and not persona_name:
            return Response(
                {"error": "Persona identifier is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_message_id = (request.data.get("client_message_id") or "").strip()
        edit_message_id = (request.data.get("edit_message_id") or "").strip()
        regenerate_bot_message_id = (request.data.get("regenerate_bot_message_id") or "").strip()
        greeting = request.data.get("greeting", "")
        memory_prompt = request.data.get("memory_prompt", "")
        persona_tagline = (request.data.get("persona_tagline") or "").strip()
        client_time = request.data.get("client_time", "")
        client_timezone = request.data.get("client_timezone", "")
        user_name = (request.data.get("user_name") or "").strip()
        user_key = (request.headers.get("X-Memory-User-Key") or request.data.get("user_key") or "").strip() or None

        user_id = request.user.id if request.user.is_authenticated else (request.data.get("user_id") or "guest")

        # Resolve user name if not explicitly provided (prioritize latest custom display name over raw OAuth given_name)
        if not user_name:
            if request.user.is_authenticated:
                user_name = getattr(request.user, "name", "") or getattr(request.user, "given_name", "")
            elif user_id and user_id != "guest":
                try:
                    from authentication.models import User
                    u = User.objects.filter(id=user_id).first()
                    if u:
                        user_name = (u.name.split()[0] if u.name else "") or u.name or u.given_name or ""
                except Exception:
                    pass

        # Strict isolation: Combine user_id + persona_id into a unique, deterministic Reeve namespace
        clean_user_id = str(user_id).strip().replace(":", "_").replace("/", "_")
        clean_persona_id = str(persona_id).strip().replace(":", "_").replace("/", "_") if persona_id else "default"
        namespace = f"usr_{clean_user_id}_persona_{clean_persona_id}"

        from .models import PersonaChatMessage

        # Resolve message to edit if edit_message_id is supplied
        user_msg_to_edit = None
        existing_bot_reply = None
        if edit_message_id:
            import uuid as uuid_pkg
            try:
                parsed_uuid = uuid_pkg.UUID(edit_message_id)
                user_msg_to_edit = PersonaChatMessage.objects.filter(
                    id=parsed_uuid,
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="user",
                ).first()
            except (ValueError, TypeError):
                pass

            if not user_msg_to_edit:
                user_msg_to_edit = PersonaChatMessage.objects.filter(
                    client_message_id=edit_message_id,
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="user",
                ).first()

            if user_msg_to_edit:
                logger.info(
                    "Processing edit for user message id=%s client_message_id=%s",
                    user_msg_to_edit.id,
                    user_msg_to_edit.client_message_id,
                )
                existing_bot_reply = PersonaChatMessage.objects.filter(
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="bot",
                    created_at__gte=user_msg_to_edit.created_at,
                ).order_by("created_at").first()

        if regenerate_bot_message_id and not existing_bot_reply:
            import uuid as uuid_pkg
            try:
                parsed_bot_uuid = uuid_pkg.UUID(regenerate_bot_message_id)
                existing_bot_reply = PersonaChatMessage.objects.filter(
                    id=parsed_bot_uuid,
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="bot",
                ).first()
            except (ValueError, TypeError):
                pass

            if not existing_bot_reply:
                existing_bot_reply = PersonaChatMessage.objects.filter(
                    client_message_id=regenerate_bot_message_id,
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="bot",
                ).first()

            if existing_bot_reply and not user_msg_to_edit:
                user_msg_to_edit = PersonaChatMessage.objects.filter(
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="user",
                    created_at__lte=existing_bot_reply.created_at,
                ).order_by("-created_at").first()

        # Client Message ID Idempotency Check (bypassed if editing or regenerating an existing message)
        existing_msg = None
        if client_message_id and not user_msg_to_edit and not regenerate_bot_message_id:
            if is_autonomous_continue:
                bot_reply = PersonaChatMessage.objects.filter(
                    client_message_id=client_message_id,
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="bot",
                ).first()
                if bot_reply:
                    replay_reply = decrypt_chat_message(
                        bot_reply.text,
                        user_id=str(user_id),
                        client_key=user_key,
                    )
                    return Response(
                        {
                            "id": str(bot_reply.id),
                            "user_message_id": None,
                            "client_message_id": client_message_id,
                            "reply": replay_reply,
                            "conflict_stage": bot_reply.conflict_stage,
                            "conflict_level": bot_reply.conflict_stage,
                            "context": "",
                            "namespace": namespace,
                            "persona_id": persona_id,
                            "user_id": str(user_id),
                            "metadata": bot_reply.response_metadata or {},
                        },
                        status=status.HTTP_200_OK,
                    )
            else:
                existing_msg = PersonaChatMessage.objects.filter(
                    client_message_id=client_message_id,
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="user",
                ).first()
                if existing_msg:
                    logger.info(
                        "Idempotency hit for client_message_id=%s",
                        client_message_id,
                    )
                    # New records: exact user-to-bot request ID association.
                    bot_reply = PersonaChatMessage.objects.filter(
                        client_message_id=client_message_id,
                        user_identifier=str(user_id),
                        persona_identifier=str(persona_id),
                        sender="bot",
                    ).order_by("created_at").first()

                    # Backward compatibility for older bot messages that did not
                    # store client_message_id.
                    if bot_reply is None:
                        bot_reply = PersonaChatMessage.objects.filter(
                            user_identifier=str(user_id),
                            persona_identifier=str(persona_id),
                            sender="bot",
                            client_message_id="",
                            created_at__gte=existing_msg.created_at,
                        ).order_by("created_at").first()

                    if bot_reply:
                        replay_reply = decrypt_chat_message(
                            bot_reply.text,
                            user_id=str(user_id),
                            client_key=user_key,
                        )
                        return Response(
                            {
                                "id": str(bot_reply.id),
                                "user_message_id": str(existing_msg.id) if existing_msg else None,
                                "client_message_id": client_message_id,
                                "reply": replay_reply,
                                "conflict_stage": bot_reply.conflict_stage,
                                "conflict_level": bot_reply.conflict_stage,
                                "context": "",
                                "namespace": namespace,
                                "persona_id": persona_id,
                                "user_id": str(user_id),
                                "metadata": bot_reply.response_metadata or {},
                            },
                            status=status.HTTP_200_OK,
                        )
                    else:
                        # Incomplete turn from a previous attempt: user message was persisted,
                        # but bot reply was not generated/saved (e.g. timeout or disconnect).
                        # Resume this turn and generate the bot reply on retry instead of rejecting with 409!
                        logger.info(
                            "Incomplete chat turn for client_message_id=%s. Resuming reply generation on retry.",
                            client_message_id,
                        )

        # Resolve persona from database if persona_id is provided
        persona_obj = None
        persona_age = None
        if persona_id:
            try:
                from .models import Persona
                from django.db.models import F
                persona_obj = Persona.objects.filter(id=persona_id).first()
                if persona_obj:
                    persona_age = persona_obj.age
                    if not persona_name:
                        persona_name = persona_obj.name
                    if not greeting:
                        greeting = persona_obj.greeting
                    if not memory_prompt:
                        memory_prompt = persona_obj.memory_prompt
                    if not persona_tagline:
                        persona_tagline = persona_obj.tagline
                    # Increment chat count
                    Persona.objects.filter(id=persona_id).update(chats_count=F("chats_count") + 1)
            except Exception:
                pass

        if not persona_name:
            persona_name = "Companion"

        # Resolve User model instance
        user_obj = request.user if request.user.is_authenticated else None
        if not user_obj and user_id and user_id != "guest":
            try:
                from authentication.models import User
                user_obj = User.objects.filter(id=user_id).first()
            except Exception:
                pass

        # Fetch relationship conflict state from database for this specific user & persona
        from .models import PersonaRelationshipState, UserPersonaCustomization
        rel_state, _ = PersonaRelationshipState.objects.get_or_create(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
        )
        current_conflict_stage = rel_state.conflict_stage
        current_story_tone = getattr(rel_state, "story_tone", "default") or "default"

        # Override persona personality & greeting with per-user customization if one exists
        try:
            user_custom = UserPersonaCustomization.objects.filter(
                user_identifier=str(user_id),
                persona_identifier=str(persona_id),
            ).first()
            if user_custom:
                if user_custom.custom_greeting:
                    greeting = user_custom.custom_greeting
                if user_custom.custom_memory_prompt:
                    memory_prompt = user_custom.custom_memory_prompt
                if user_custom.custom_name:
                    persona_name = user_custom.custom_name
                if user_custom.custom_tagline:
                    persona_tagline = user_custom.custom_tagline
        except Exception as exc:
            logger.warning("Error checking user persona customization: %s", exc)

        # Fetch up to 10 recent messages from PostgreSQL for immediate conversational continuity.
        exclude_turn_ids = []
        if user_msg_to_edit:
            exclude_turn_ids.append(user_msg_to_edit.id)
            if existing_bot_reply:
                exclude_turn_ids.append(existing_bot_reply.id)

        turns_filter = PersonaChatMessage.objects.filter(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
        )
        if exclude_turn_ids:
            turns_filter = turns_filter.exclude(id__in=exclude_turn_ids)

        recent_turns_qs = list(turns_filter.order_by("-created_at")[:10])
        recent_turns_qs.reverse()
        conversation_history = [
            {
                "role": "user" if m.sender == "user" else "assistant",
                "content": decrypt_chat_message(m.text, user_id=str(user_id), client_key=user_key),
            }
            for m in recent_turns_qs
        ]

        # Automatic Client-Key Handover on post
        if user_key:
            try:
                migrate_user_messages_to_client_key(str(user_id), user_key)
            except Exception as exc:
                logger.warning("Error during client-key handover on post: %s", type(exc).__name__)

        # 1. Store or update user message in PostgreSQL (skipped during autonomous continue)
        user_msg_record = None
        newly_created_user_msg = False
        if not is_autonomous_continue:
            if user_msg_to_edit:
                try:
                    if not regenerate_bot_message_id:
                        encrypted_user_msg = encrypt_chat_message(message, user_id=str(user_id), client_key=user_key)
                        user_msg_to_edit.text = encrypted_user_msg
                        if client_message_id:
                            user_msg_to_edit.client_message_id = client_message_id
                        user_msg_to_edit.save(update_fields=["text", "client_message_id"])
                        logger.info("Updated edited message in PostgreSQL id=%s", user_msg_to_edit.id)
                    user_msg_record = user_msg_to_edit
                except Exception as e:
                    logger.warning(f"Could not update edited user message in DB: {e}")
            elif existing_msg:
                user_msg_record = existing_msg
            else:
                # Clean up any trailing orphaned incomplete user message at the tail of the conversation
                # so retrying never leaves duplicate or unanswered user messages in PostgreSQL
                try:
                    last_turn = PersonaChatMessage.objects.filter(
                        user_identifier=str(user_id),
                        persona_identifier=str(persona_id),
                    ).order_by("-created_at").first()
                    if last_turn and last_turn.sender == "user":
                        has_subsequent_reply = PersonaChatMessage.objects.filter(
                            user_identifier=str(user_id),
                            persona_identifier=str(persona_id),
                            sender="bot",
                            created_at__gte=last_turn.created_at,
                        ).exists()
                        if not has_subsequent_reply:
                            logger.info(
                                "Cleaning up trailing orphaned incomplete user message id=%s before creating turn.",
                                last_turn.id,
                            )
                            last_turn.delete()
                except Exception as exc:
                    logger.warning(f"Error checking trailing incomplete turn: {exc}")

                try:
                    encrypted_user_msg = encrypt_chat_message(message, user_id=str(user_id), client_key=user_key)
                    user_msg_record = PersonaChatMessage.objects.create(
                        user=user_obj,
                        user_identifier=str(user_id),
                        persona=persona_obj,
                        persona_identifier=str(persona_id),
                        namespace=namespace,
                        sender="user",
                        text=encrypted_user_msg,
                        conflict_stage=current_conflict_stage,
                        client_message_id=client_message_id,
                    )
                    newly_created_user_msg = True
                except Exception as e:
                    logger.warning(f"Could not persist user message to DB: {e}")

        # 2. Generate companion reply (single-prompt roleplay engine with Reeve memory and Postgres history)
        reply_length = (
            request.data.get("reply_length")
            or (getattr(user_obj, "reply_length", None) if user_obj else None)
            or "default"
        )
        if isinstance(reply_length, str):
            reply_length = reply_length.strip().lower()
        if reply_length not in ("default", "short", "long"):
            reply_length = "default"

        try:
            result = generate_companion_reply(
                message=message,
                namespace=namespace,
                persona_name=persona_name,
                persona_age=persona_age,
                persona_tagline=persona_tagline,
                greeting=greeting,
                memory_prompt=memory_prompt,
                client_time=client_time,
                client_timezone=client_timezone,
                user_name=user_name,
                conversation_history=conversation_history,
                current_conflict_stage=current_conflict_stage,
                user_key=user_key,
                persist_exchange_to_memory=False,
                reply_length=reply_length,
                is_autonomous_continue=is_autonomous_continue,
                story_tone=current_story_tone,
            )

            if result.get("success") is False:
                error_info = result.get("error", {})
                logger.error(
                    "Companion generation failed. namespace=%s error=%s",
                    namespace,
                    error_info,
                )
                # Rollback unfulfilled user message if newly created to keep database persisted chat clean
                if newly_created_user_msg and user_msg_record:
                    try:
                        user_msg_record.delete()
                    except Exception:
                        pass
                return Response(
                    {
                        "error": "Unable to generate a companion response.",
                        "code": error_info.get("code", "COMPANION_GENERATION_FAILED"),
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            reply_text = result.get("reply", "").strip()
            if not reply_text:
                if newly_created_user_msg and user_msg_record:
                    try:
                        user_msg_record.delete()
                    except Exception:
                        pass
                return Response(
                    {"error": "Failed to generate companion reply from model"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            new_conflict_stage = result.get(
                "conflict_stage",
                current_conflict_stage,
            )
            resulting_story_tone = result.get("story_tone", current_story_tone)

            try:
                with transaction.atomic():
                    # Persist updated conflict stage and immediate tone escalation only after a usable reply exists
                    update_rel_fields = []
                    if rel_state.conflict_stage != new_conflict_stage:
                        rel_state.conflict_stage = new_conflict_stage
                        update_rel_fields.append("conflict_stage")
                    if getattr(rel_state, "story_tone", None) != resulting_story_tone:
                        rel_state.story_tone = resulting_story_tone
                        update_rel_fields.append("story_tone")
                    if update_rel_fields:
                        update_rel_fields.append("updated_at")
                        rel_state.save(update_fields=update_rel_fields)

                    response_metadata = {
                        "engine": "single_prompt_roleplay",
                        "model": result.get("model", ""),
                    }

                    # Store or update bot response in PostgreSQL
                    old_reply_encrypted = existing_bot_reply.text if existing_bot_reply else None
                    encrypted_bot_msg = encrypt_chat_message(
                        reply_text,
                        user_id=str(user_id),
                        client_key=user_key,
                    )
                    if existing_bot_reply:
                        resp_meta = dict(existing_bot_reply.response_metadata or {})
                        raw_variants = list(resp_meta.get("variants") or [])
                        if not raw_variants:
                            raw_variants = [existing_bot_reply.text]

                        raw_variants.append(encrypted_bot_msg)
                        active_variant_idx = len(raw_variants) - 1

                        resp_meta["engine"] = "single_prompt_roleplay"
                        resp_meta["model"] = result.get("model", "")
                        resp_meta["variants"] = raw_variants
                        resp_meta["active_variant_index"] = active_variant_idx
                        resp_meta["reply_length"] = reply_length

                        existing_bot_reply.text = encrypted_bot_msg
                        existing_bot_reply.conflict_stage = new_conflict_stage
                        if client_message_id:
                            existing_bot_reply.client_message_id = client_message_id
                        existing_bot_reply.response_metadata = resp_meta
                        existing_bot_reply.save(update_fields=["text", "conflict_stage", "client_message_id", "response_metadata"])
                        bot_msg_id = str(existing_bot_reply.id)
                        response_metadata = resp_meta

                        decrypted_variants = [
                            decrypt_chat_message(v, user_id=str(user_id), client_key=user_key)
                            for v in raw_variants
                        ]
                        logger.info(
                            "Appended variant %d to bot response id=%s namespace=%s",
                            len(raw_variants),
                            bot_msg_id,
                            namespace,
                        )
                    else:
                        response_metadata = {
                            "engine": "single_prompt_roleplay",
                            "model": result.get("model", ""),
                            "variants": [encrypted_bot_msg],
                            "active_variant_index": 0,
                            "reply_length": reply_length,
                        }
                        bot_msg_record = PersonaChatMessage.objects.create(
                            user=user_obj,
                            user_identifier=str(user_id),
                            persona=persona_obj,
                            persona_identifier=str(persona_id),
                            namespace=namespace,
                            sender="bot",
                            text=encrypted_bot_msg,
                            conflict_stage=new_conflict_stage,
                            client_message_id=client_message_id,
                            response_metadata=response_metadata,
                        )
                        bot_msg_id = str(bot_msg_record.id)
                        active_variant_idx = 0
                        decrypted_variants = [reply_text]
                        logger.info(
                            "Persisted conversation turn namespace=%s bot_msg_id=%s",
                            namespace,
                            bot_msg_id,
                        )

                    # Publish the completed exchange to Reeve after PostgreSQL transaction commits
                    def store_committed_exchange():
                        try:
                            if old_reply_encrypted and old_reply_encrypted != encrypted_bot_msg:
                                from .reeve_service import delete_memory_for_message
                                old_reply_decrypted = decrypt_chat_message(old_reply_encrypted, user_id=str(user_id), client_key=user_key)
                                delete_memory_for_message(old_reply_decrypted, namespace=namespace, sender="bot", user_key=user_key)

                            mem_entry = (
                                f"Assistant: {reply_text}"
                                if is_autonomous_continue
                                else f"User: {message.strip()}\nAssistant: {reply_text}"
                            )
                            store_memory_for_user(
                                mem_entry,
                                namespace,
                                user_key=user_key,
                            )
                        except Exception:
                            logger.exception(
                                "Committed chat turn could not be stored in Reeve (namespace=%s).",
                                namespace,
                            )

                    transaction.on_commit(store_committed_exchange)

            except Exception as e:
                logger.exception("Failed to commit conversation turn in PostgreSQL: %s", e)
                if newly_created_user_msg and user_msg_record:
                    try:
                        user_msg_record.delete()
                    except Exception:
                        pass
                return Response(
                    {
                        "error": "Failed to persist conversation turn.",
                        "code": "CONVERSATION_PERSISTENCE_FAILED",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "id": bot_msg_id,
                    "user_message_id": str(user_msg_record.id) if user_msg_record else None,
                    "client_message_id": client_message_id,
                    "reply": reply_text,
                    "variants": decrypted_variants,
                    "active_variant_index": active_variant_idx,
                    "conflict_stage": new_conflict_stage,
                    "conflict_level": new_conflict_stage,
                    "context": result.get("context", ""),
                    "namespace": namespace,
                    "persona_id": persona_id,
                    "user_id": str(user_id),
                    "reply_length": reply_length,
                    "metadata": response_metadata,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error("Companion chat error: %s", type(e).__name__)
            return Response(
                {"error": "Companion chat service encountered an error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request):
        """
        Permanently delete an individual chat message from PostgreSQL.
        Strictly verifies ownership: user can only delete messages from their own conversation.
        """
        message_id = (request.query_params.get("message_id") or request.data.get("message_id", "")).strip()
        user_id = (request.user.id if request.user.is_authenticated else (request.query_params.get("user_id") or request.data.get("user_id", ""))).strip()

        if not message_id:
            return Response({"error": "message_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not user_id:
            return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        import uuid as uuid_pkg
        from django.db import transaction
        from .models import PersonaChatMessage

        parsed_uuid = None
        try:
            parsed_uuid = uuid_pkg.UUID(message_id)
        except (ValueError, TypeError):
            pass

        if parsed_uuid:
            msg_qs = PersonaChatMessage.objects.filter(id=parsed_uuid, user_identifier=str(user_id))
        else:
            msg_qs = PersonaChatMessage.objects.filter(
                client_message_id=message_id,
                user_identifier=str(user_id),
                sender="user",
            )
            if not msg_qs.exists():
                msg_qs = PersonaChatMessage.objects.filter(
                    client_message_id=message_id,
                    user_identifier=str(user_id),
                )

        target_msg = msg_qs.first()
        if not target_msg:
            return Response(
                {"error": "Message not found or unauthorized to delete"},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted_id = str(target_msg.id)
        namespace = target_msg.namespace
        sender = target_msg.sender
        user_key = (request.headers.get("X-Memory-User-Key") or request.query_params.get("user_key") or request.data.get("user_key") or "").strip() or None

        # Decrypt message content before deleting row from PostgreSQL
        from .crypto import decrypt_chat_message
        deleted_text = decrypt_chat_message(target_msg.text, user_id=str(user_id), client_key=user_key)

        with transaction.atomic():
            target_msg.delete()

        # Level 2 Deletion: Prune Reeve Memory Graph and WriteBuffer
        reeve_pruned = 0
        try:
            from .reeve_service import delete_memory_for_message
            reeve_pruned = delete_memory_for_message(
                deleted_text,
                namespace=namespace,
                sender=sender,
                user_key=user_key,
            )
        except Exception as exc:
            logger.warning("Could not prune Reeve memory for message id=%s: %s", deleted_id, exc)

        logger.info("Deleted chat message id=%s (Reeve episodes pruned: %d) for user=%s", deleted_id, reeve_pruned, user_id)
        return Response(
            {"success": True, "deleted_id": deleted_id, "reeve_episodes_pruned": reeve_pruned},
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        """
        Switch active response variant for a regenerated bot message, OR
        edit a persona's response in-place and synchronize both PostgreSQL and Reeve memory graph.
        """
        message_id = (request.data.get("message_id") or request.query_params.get("message_id", "")).strip()
        user_id = (request.user.id if request.user.is_authenticated else (request.data.get("user_id") or request.query_params.get("user_id", ""))).strip()
        new_text = (request.data.get("text") or "").strip()
        variant_index = request.data.get("variant_index")

        if not message_id:
            return Response({"error": "message_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not user_id:
            return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not new_text and variant_index is None:
            return Response({"error": "Either 'text' to edit or 'variant_index' to switch is required"}, status=status.HTTP_400_BAD_REQUEST)

        import uuid as uuid_pkg
        from .models import PersonaChatMessage
        from .crypto import encrypt_chat_message, decrypt_chat_message
        user_key = (request.headers.get("X-Memory-User-Key") or request.query_params.get("user_key") or request.data.get("user_key") or "").strip() or None

        target_msg = None
        try:
            parsed_uuid = uuid_pkg.UUID(message_id)
            target_msg = PersonaChatMessage.objects.filter(
                id=parsed_uuid,
                user_identifier=str(user_id),
                sender="bot",
            ).first()
        except (ValueError, TypeError):
            pass

        if not target_msg:
            target_msg = PersonaChatMessage.objects.filter(
                client_message_id=message_id,
                user_identifier=str(user_id),
                sender="bot",
            ).first()

        if not target_msg:
            return Response({"error": "Bot message not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        # -------------------------------------------------------------------------
        # Branch A: In-place edit of persona response by user
        # -------------------------------------------------------------------------
        if new_text:
            old_decrypted_text = decrypt_chat_message(target_msg.text, user_id=str(user_id), client_key=user_key)
            encrypted_new_text = encrypt_chat_message(new_text, user_id=str(user_id), client_key=user_key)
            target_msg.text = encrypted_new_text

            resp_meta = dict(target_msg.response_metadata or {})
            variants = resp_meta.get("variants") or []
            active_idx = resp_meta.get("active_variant_index", 0)
            if variants:
                if 0 <= active_idx < len(variants):
                    variants[active_idx] = encrypted_new_text
                else:
                    variants.append(encrypted_new_text)
                resp_meta["variants"] = variants
                resp_meta["active_variant_index"] = active_idx
                target_msg.response_metadata = resp_meta

            target_msg.save(update_fields=["text", "response_metadata"])

            # Synchronize Reeve Long-Term Memory with the edited text
            try:
                user_msg = PersonaChatMessage.objects.filter(
                    user_identifier=str(user_id),
                    persona_identifier=target_msg.persona_identifier,
                    sender="user",
                    created_at__lte=target_msg.created_at,
                ).order_by("-created_at").first()

                from .reeve_service import delete_memory_for_message, store_memory_for_user

                # Prune old bot response from Reeve memory graph and write buffer
                delete_memory_for_message(
                    old_decrypted_text,
                    namespace=target_msg.namespace,
                    sender="bot",
                    user_key=user_key,
                )

                # Ingest updated persona text into Reeve
                if user_msg:
                    user_text = decrypt_chat_message(user_msg.text, user_id=str(user_id), client_key=user_key)
                    store_memory_for_user(
                        f"User: {user_text.strip()}\nAssistant: {new_text.strip()}",
                        target_msg.namespace,
                        user_key=user_key,
                    )
                else:
                    store_memory_for_user(
                        f"Assistant: {new_text.strip()}",
                        target_msg.namespace,
                        user_key=user_key,
                    )
            except Exception as exc:
                logger.warning("Could not sync Reeve memory for edited bot response: %s", exc)

            logger.info(
                "Edited bot message id=%s in PostgreSQL and Reeve for user=%s",
                target_msg.id,
                user_id,
            )

            decrypted_variants = [
                decrypt_chat_message(v, user_id=str(user_id), client_key=user_key)
                for v in variants
            ] if variants else [new_text]

            return Response(
                {
                    "success": True,
                    "message_id": str(target_msg.id),
                    "text": new_text,
                    "variants": decrypted_variants,
                    "variants_count": len(decrypted_variants),
                },
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------------------------------
        # Branch B: Switch active variant (0-indexed)
        # -------------------------------------------------------------------------
        try:
            variant_index = int(variant_index)
        except (ValueError, TypeError):
            return Response({"error": "variant_index must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        resp_meta = dict(target_msg.response_metadata or {})
        variants = resp_meta.get("variants") or []

        if not variants:
            return Response({"error": "Message has no variants to switch"}, status=status.HTTP_400_BAD_REQUEST)

        if variant_index < 0 or variant_index >= len(variants):
            return Response({"error": f"variant_index out of range (0..{len(variants)-1})"}, status=status.HTTP_400_BAD_REQUEST)

        chosen_variant_encrypted = variants[variant_index]
        target_msg.text = chosen_variant_encrypted
        resp_meta["active_variant_index"] = variant_index
        target_msg.response_metadata = resp_meta
        target_msg.save(update_fields=["text", "response_metadata"])

        decrypted_text = decrypt_chat_message(chosen_variant_encrypted, user_id=str(user_id), client_key=user_key)
        decrypted_variants = [
            decrypt_chat_message(v, user_id=str(user_id), client_key=user_key)
            for v in variants
        ]

        # Synchronize Reeve Long-Term Memory with the selected variant
        try:
            user_msg = PersonaChatMessage.objects.filter(
                user_identifier=str(user_id),
                persona_identifier=target_msg.persona_identifier,
                sender="user",
                created_at__lte=target_msg.created_at,
            ).order_by("-created_at").first()

            if user_msg:
                user_text = decrypt_chat_message(user_msg.text, user_id=str(user_id), client_key=user_key)
                from .reeve_service import delete_memory_for_message, store_memory_for_user

                for i, v in enumerate(variants):
                    if i != variant_index:
                        unselected_decrypted = decrypt_chat_message(v, user_id=str(user_id), client_key=user_key)
                        delete_memory_for_message(unselected_decrypted, namespace=target_msg.namespace, sender="bot", user_key=user_key)

                store_memory_for_user(
                    f"User: {user_text.strip()}\nAssistant: {decrypted_text}",
                    target_msg.namespace,
                    user_key=user_key,
                )
        except Exception as exc:
            logger.warning("Could not sync Reeve memory for switched variant: %s", exc)

        logger.info(
            "Switched bot message id=%s to variant %d/%d in PostgreSQL for user=%s",
            target_msg.id,
            variant_index + 1,
            len(variants),
            user_id,
        )

        return Response(
            {
                "success": True,
                "message_id": str(target_msg.id),
                "text": decrypted_text,
                "active_variant_index": variant_index,
                "variants": decrypted_variants,
                "variants_count": len(variants),
            },
            status=status.HTTP_200_OK,
        )

class StoreMemoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"error": "text is required"}, status=status.HTTP_400_BAD_REQUEST)

        user_key = (request.headers.get("X-Memory-User-Key") or request.data.get("user_key") or request.query_params.get("user_key") or "").strip() or None
        res = store_memory_for_user(text, request.user.namespace, user_key=user_key)
        return Response({"status": "stored", "namespace": request.user.namespace, "result": res})

class QueryMemoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = request.data.get("question", "").strip()
        if not question:
            return Response({"error": "question is required"}, status=status.HTTP_400_BAD_REQUEST)

        user_key = (request.headers.get("X-Memory-User-Key") or request.data.get("user_key") or request.query_params.get("user_key") or "").strip() or None
        answer = query_memory_for_user(question, request.user.namespace, user_key=user_key)
        context = retrieve_context_for_user(question, request.user.namespace, user_key=user_key)
        return Response({
            "answer": answer,
            "context": context,
            "namespace": request.user.namespace,
        })

class ClearMemoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        clear_user_memories(request.user.namespace)
        return Response({"status": "cleared", "namespace": request.user.namespace})


class BotImageUploadView(APIView):
    """
    Uploads bot avatar to AWS S3.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        import os
        import uuid
        import boto3

        import base64
        import io

        file_obj = request.FILES.get('image')
        image_b64 = request.data.get('image_base64')

        if not file_obj and not image_b64:
            return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)

        if image_b64:
            # Decode base64
            if ',' in image_b64:
                image_b64 = image_b64.split(',', 1)[1]
            image_data = base64.b64decode(image_b64)
            file_stream = io.BytesIO(image_data)
            filename = f"bot_pictures/{uuid.uuid4().hex}.jpg"
            content_type = 'image/jpeg'
        else:
            ext = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else 'jpg'
            filename = f"bot_pictures/{uuid.uuid4().hex}.{ext}"
            content_type = file_obj.content_type or 'image/jpeg'
            file_stream = file_obj

        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-west-2')
        )
        bucket = 'reeve-devpilot-downloads-309490998255'

        try:
            s3.upload_fileobj(
                file_stream,
                bucket,
                filename,
                ExtraArgs={'ContentType': content_type}
            )
            region = os.getenv('AWS_REGION', 'us-west-2')
            image_url = f"https://{bucket}.s3.{region}.amazonaws.com/{filename}"
            return Response({
                "url": image_url,
                "key": filename,
                "success": True
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenerateAvatarPersonaView(APIView):
    """
    Generates avatar personas, names, first messages (scene openers), and rich character memory profiles
    using Groq (qwen/qwen3.8-27b) with Bedrock fallback for immersive romantic and companion dynamics
    (e.g. girlfriend, boyfriend, husband, roommate, enemies-to-lovers, blind date).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        import os
        import json
        import re
        import requests
        from django.conf import settings
        from response_generator import strip_emojis

        field = request.data.get("field", "all")
        avatar_name = (request.data.get("name") or "").strip()
        tagline = (request.data.get("tagline") or "").strip()

        char_desc = f"{avatar_name} ({tagline})" if avatar_name and tagline else (avatar_name or tagline or "a compelling romantic companion")

        if field == "name":
            system_prompt = (
                "You are an expert character designer for Amour, an intimate AI companion and relationship roleplay platform. "
                "The app is designed for deep romantic and emotional connections between user and persona "
                "(such as affectionate girlfriend, protective boyfriend, devoted husband or wife, sassy flirty roommate, enemies-to-lovers rival, or charming blind date). "
                "NEVER generate corporate, robotic, assistant, or professional resume personas. "
                "Suggest 1 unique persona name, a realistic age (integer between 20 and 28), and an evocative relationship tagline capturing their dynamic with the user. "
                "STRICT RULE: Absolutely ZERO emojis anywhere. "
                "Respond ONLY in valid JSON: {\"name\": \"...\", \"age\": 22, \"tagline\": \"...\"}"
            )
            user_prompt = "Give me 1 creative romantic companion name, age, and relationship tagline."
        elif field == "greeting":
            system_prompt = (
                f"You are crafting the opening first message for the character {char_desc}. "
                "Write an immersive opening scene starter that immediately hooks the user into the roleplay. "
                "Combine vivid narrative actions in asterisks *...* (what the character is doing, physical gestures, setting the scene) "
                "with their spoken dialogue to establish their chemistry and dynamic with the user. "
                "Keep it timeless (do not assume morning or bedtime unless specified in their premise). "
                "STRICT RULE: Absolutely ZERO emojis. "
                "Respond ONLY in valid JSON: {\"greeting\": \"...\"}"
            )
            user_prompt = "Write the opening scene and first message for this character."
        elif field == "memory":
            system_prompt = (
                f"You are defining the core backstory and memory profile for {char_desc}. "
                "Amour is a character roleplay app for romantic and interpersonal connections. "
                "NEVER write a corporate resume or clinical bullet points. "
                "Write a rich character mind and relationship profile covering:\n"
                "- Relationship & Dynamic with the user (e.g. girlfriend, boyfriend, roommate with unspoken feelings, rival, spouse)\n"
                "- Personality, Quirks & Emotional Reactions (how they behave when happy, shy, teasing, or protective)\n"
                "- Core memories and shared lore with the user\n"
                "- Conversational Tone (casual texting style, zero emojis)\n"
                "STRICT RULE: Absolutely ZERO emojis. "
                "Respond ONLY in valid JSON: {\"memory\": \"...\"}"
            )
            user_prompt = "Generate the character memory and backstory profile."
        else:
            system_prompt = (
                "You are an expert character designer for Amour, an intimate AI companion and relationship roleplay platform. "
                "Generate a complete romantic companion profile (such as girlfriend, boyfriend, roommate, husband, or rival). "
                "NEVER generate professional or corporate personas. "
                "Include:\n"
                "1. name\n"
                "2. age (integer between 20 and 28)\n"
                "3. tagline (relationship dynamic)\n"
                "4. greeting (immersive opening scene with *actions* and dialogue)\n"
                "5. memory (rich character mind, dynamic, quirks, and texting tone)\n"
                "STRICT RULE: Absolutely ZERO emojis. "
                "Respond ONLY in valid JSON: {\"name\": \"...\", \"age\": 22, \"tagline\": \"...\", \"greeting\": \"...\", \"memory\": \"...\"}"
            )
            user_prompt = "Generate a complete companion profile."

        # 1. Primary Engine: Groq LLM (High speed, creative roleplay, guaranteed JSON format)
        groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        llm_base_url = (getattr(settings, "LLM_BASE_URL", "") or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        llm_model = getattr(settings, "LLM_MODEL", "") or os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")

        if groq_api_key:
            try:
                payload = {
                    "model": llm_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.85,
                    "max_tokens": 500,
                    "response_format": {"type": "json_object"},
                }
                resp = requests.post(
                    f"{llm_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=15,
                )
                if resp.status_code == 200:
                    content_str = resp.json()["choices"][0]["message"]["content"]
                    parsed = json.loads(content_str)
                    for k, v in parsed.items():
                        if isinstance(v, str):
                            parsed[k] = strip_emojis(v).strip()
                    return Response(parsed)
            except Exception as e:
                logger.warning(f"Groq persona generation error, falling back to Bedrock: {e}")

        # 2. Fallback Engine: AWS Bedrock Llama 3.1
        try:
            import boto3
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_region = os.getenv("AWS_REGION", "us-west-2")
            model_id = os.getenv("BEDROCK_SMALL_MODEL_ID", "meta.llama3-1-8b-instruct-v1:0")

            client = boto3.client(
                "bedrock-runtime",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region,
            )
            llama_prompt = (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n{system_prompt}<|eot_id|>\n"
                f"<|start_header_id|>user<|end_header_id|>\n{user_prompt}<|eot_id|>\n"
                f"<|start_header_id|>assistant<|end_header_id|>\n"
            )
            body = json.dumps({
                "prompt": llama_prompt,
                "max_gen_len": 450,
                "temperature": 0.85,
            })
            resp = client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            raw = json.loads(resp["body"].read())
            gen_text = raw.get("generation", "").strip()

            clean_str = gen_text.strip()
            start_idx = clean_str.find("{")
            end_idx = clean_str.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                parsed = json.loads(clean_str[start_idx : end_idx + 1])
                for k, v in parsed.items():
                    if isinstance(v, str):
                        parsed[k] = strip_emojis(v).strip()
                return Response(parsed)
            return Response({"raw": strip_emojis(gen_text)})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PersonaListCreateView(APIView):
    """
    Lists personas from PostgreSQL database (Neon) or creates a new Persona
    forged in Amour Studio. Supports pagination for high-performance home feed.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import Persona
        from .serializers import PersonaSerializer

        scope = request.query_params.get("scope")
        creator_id = request.query_params.get("creator_id") or request.query_params.get("user_id")
        visibility = request.query_params.get("visibility")
        queryset = Persona.objects.all().order_by("-created_at")

        if creator_id:
            queryset = queryset.filter(creator_id=creator_id)
        elif scope == "my_personas":
            # If scope is my_personas and no creator_id passed, return empty or non-community
            queryset = queryset.filter(is_community=False)
        elif scope == "community":
            queryset = queryset.filter(is_community=True)

        if visibility in ["public", "private"]:
            queryset = queryset.filter(visibility=visibility)

        page_param = request.query_params.get("page")
        if page_param is not None:
            try:
                page = max(1, int(page_param))
            except ValueError:
                page = 1
            try:
                page_size = max(1, min(50, int(request.query_params.get("page_size", 5))))
            except ValueError:
                page_size = 5

            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            items = queryset[start:end]
            serializer = PersonaSerializer(items, many=True)
            return Response({
                "results": serializer.data,
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "has_more": end < total_count,
            }, status=status.HTTP_200_OK)

        serializer = PersonaSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        from .models import Persona
        from .serializers import PersonaSerializer
        from django.contrib.auth import get_user_model

        User = get_user_model()
        data = request.data.copy()

        # Sanitize any invalid local device file URIs
        raw_image_url = data.get("image_url", "")
        if raw_image_url.startswith("file://") or raw_image_url.startswith("content://"):
            data["image_url"] = ""

        # If base64 payload provided without valid S3 url, upload to S3 directly
        image_b64 = data.get("image_base64")
        if image_b64 and not data.get("image_url"):
            try:
                import io, uuid, boto3, base64
                if ',' in image_b64:
                    image_b64 = image_b64.split(',', 1)[1]
                image_data = base64.b64decode(image_b64)
                file_stream = io.BytesIO(image_data)
                filename = f"bot_pictures/{uuid.uuid4().hex}.jpg"
                s3 = boto3.client(
                    's3',
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                    region_name=os.getenv('AWS_REGION', 'us-west-2')
                )
                bucket = os.getenv('AWS_S3_BUCKET_NAME', 'reeve-devpilot-downloads-309490998255')
                s3.upload_fileobj(file_stream, bucket, filename, ExtraArgs={'ContentType': 'image/jpeg'})
                region = os.getenv('AWS_REGION', 'us-west-2')
                data['image_url'] = f"https://{bucket}.s3.{region}.amazonaws.com/{filename}"
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"S3 persona image upload failed: {e}")

        user_id = data.get("user_id") or data.get("creator_id")
        creator = None
        if user_id:
            creator = User.objects.filter(id=str(user_id)).first()
        if not creator and request.user and request.user.is_authenticated:
            creator = request.user

        serializer = PersonaSerializer(data=data)
        if serializer.is_valid():
            persona = serializer.save(creator=creator)
            updated_fields = []
            if creator:
                if not persona.publisher_name:
                    persona.publisher_name = creator.name or creator.email.split('@')[0]
                    updated_fields.append("publisher_name")
                if not persona.publisher_avatar and creator.picture:
                    persona.publisher_avatar = creator.picture
                    updated_fields.append("publisher_avatar")
                if not persona.publisher_handle:
                    persona.publisher_handle = f"@{creator.email.split('@')[0]}"
                    updated_fields.append("publisher_handle")
            if persona.visibility == "public" and not persona.is_community:
                persona.is_community = True
                updated_fields.append("is_community")
            if updated_fields:
                persona.save(update_fields=updated_fields)
            return Response(PersonaSerializer(persona).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PersonaLikeToggleView(APIView):
    """
    Toggles a like on a persona card in the home feed.
    Connects the user ID who liked to the persona and the persona's poster ID.
    Always maintains authoritative database-synced count.
    """
    permission_classes = [AllowAny]

    def post(self, request, persona_id):
        from .models import Persona, PersonaLike
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            persona = Persona.objects.get(id=persona_id)
        except Persona.DoesNotExist:
            return Response({"error": "Persona not found"}, status=status.HTTP_404_NOT_FOUND)

        user_id = request.data.get("user_id")
        user_obj = None
        if user_id:
            user_obj = User.objects.filter(id=str(user_id)).first()
        if not user_obj and request.user and request.user.is_authenticated:
            user_obj = request.user
            user_id = str(user_obj.id)
        if not user_id:
            client_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR") or "client"
            user_id = f"guest_{client_ip}"
        user_id = str(user_id)

        # Persona poster information (user who created/posted the persona)
        poster_obj = persona.creator
        poster_id = str(persona.creator_id or persona.publisher_handle or "")

        existing = PersonaLike.objects.filter(persona=persona, user_identifier=user_id).first()
        if existing:
            existing.delete()
            liked = False
        else:
            PersonaLike.objects.create(
                persona=persona,
                user=user_obj,
                user_identifier=user_id,
                poster=poster_obj,
                poster_identifier=poster_id,
            )
            liked = True

        # Compute accurate count from database
        persona.likes_count = PersonaLike.objects.filter(persona=persona).count()
        persona.save(update_fields=["likes_count"])

        return Response({
            "liked": liked,
            "likes_count": persona.likes_count,
            "persona_id": str(persona.id),
            "user_id": user_id,
            "poster_id": poster_id,
            "persona_name": persona.name,
        }, status=status.HTTP_200_OK)


class PublisherFollowToggleView(APIView):
    """
    Toggles follow / unfollow for a persona creator / publisher associated with user ID.
    """
    permission_classes = [AllowAny]

    def post(self, request, handle):
        from .models import PublisherFollow

        clean_handle = handle.strip()
        normalized_handle = f"@{clean_handle.lstrip('@')}"
        bare_handle = clean_handle.lstrip("@")
        user_id = request.data.get("user_id")
        if request.user and request.user.is_authenticated:
            user_id = str(request.user.id)
        if not user_id:
            client_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR") or "client"
            user_id = f"guest_{client_ip}"
        user_id = str(user_id)

        existing = PublisherFollow.objects.filter(
            publisher_handle__in=[clean_handle, normalized_handle, bare_handle],
            user_identifier=user_id
        ).first()

        if existing:
            existing.delete()
            following = False
        else:
            PublisherFollow.objects.create(publisher_handle=normalized_handle, user_identifier=user_id)
            following = True

        followers_count = PublisherFollow.objects.filter(
            publisher_handle__in=[clean_handle, normalized_handle, bare_handle]
        ).count()

        return Response({
            "following": following,
            "followers_count": followers_count,
            "handle": normalized_handle,
            "user_id": user_id,
        }, status=status.HTTP_200_OK)


class UserInteractionsView(APIView):
    """
    Returns lists of liked persona IDs and followed publisher handles for a user.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import PersonaLike, PublisherFollow

        user_id = request.query_params.get("user_id")
        if not user_id and request.user and request.user.is_authenticated:
            user_id = str(request.user.id)
        if not user_id:
            return Response({"liked_ids": [], "followed_handles": []}, status=status.HTTP_200_OK)

        user_id = str(user_id)
        liked_ids = list(PersonaLike.objects.filter(user_identifier=user_id).values_list("persona_id", flat=True))
        followed = list(PublisherFollow.objects.filter(user_identifier=user_id).values_list("publisher_handle", flat=True))

        followed_handles = []
        for h in followed:
            norm = f"@{h.lstrip('@')}"
            bare = h.lstrip("@")
            if norm not in followed_handles:
                followed_handles.append(norm)
            if bare not in followed_handles:
                followed_handles.append(bare)

        return Response({
            "liked_ids": [str(lid) for lid in liked_ids],
            "followed_handles": followed_handles,
        }, status=status.HTTP_200_OK)


class PublisherProfileView(APIView):
    """
    Returns publisher profile details including real profile picture,
    name, handle, follower counts, and all public personas published by them.
    """
    permission_classes = [AllowAny]

    def get(self, request, identifier):
        from .models import Persona, PublisherFollow
        from .serializers import PersonaSerializer
        from django.contrib.auth import get_user_model

        User = get_user_model()
        clean = identifier.strip()
        user = User.objects.filter(id=clean).first()
        if not user:
            user = User.objects.filter(email=clean).first()
        if not user and clean.startswith("@"):
            user = User.objects.filter(email__istartswith=clean[1:]).first()

        sample_persona = None
        if not user:
            sample_persona = Persona.objects.filter(publisher_handle__iexact=clean).first()
            if not sample_persona and not clean.startswith("@"):
                sample_persona = Persona.objects.filter(publisher_handle__iexact=f"@{clean}").first()
            if sample_persona and sample_persona.creator:
                user = sample_persona.creator

        publisher_name = user.name if user else (sample_persona.publisher_name if sample_persona and sample_persona.publisher_name else clean.replace("@", "").capitalize())
        publisher_avatar = user.picture if (user and user.picture) else (sample_persona.publisher_avatar if sample_persona and sample_persona.publisher_avatar else "")
        publisher_handle = f"@{user.email.split('@')[0]}" if user else (sample_persona.publisher_handle if sample_persona and sample_persona.publisher_handle else (clean if clean.startswith("@") else f"@{clean}"))

        if user:
            personas = Persona.objects.filter(creator=user, visibility="public")
        else:
            personas = Persona.objects.filter(publisher_handle=publisher_handle, visibility="public")

        followers_count = PublisherFollow.objects.filter(
            publisher_handle__in=[publisher_handle, publisher_handle.lstrip("@"), f"@{publisher_handle.lstrip('@')}"]
        ).count()
        current_user_id = request.query_params.get("user_id") or (str(request.user.id) if request.user and request.user.is_authenticated else "guest")
        is_following = PublisherFollow.objects.filter(
            publisher_handle__in=[publisher_handle, publisher_handle.lstrip("@"), f"@{publisher_handle.lstrip('@')}"],
            user_identifier=str(current_user_id)
        ).exists()

        serializer = PersonaSerializer(personas, many=True)
        return Response({
            "name": publisher_name,
            "handle": publisher_handle,
            "avatar": publisher_avatar,
            "followers_count": followers_count,
            "personas_count": personas.count(),
            "is_following": is_following,
            "personas": serializer.data,
        }, status=status.HTTP_200_OK)


class PersonaDetailView(APIView):
    """
    Retrieves, updates, or deletes a single persona from the database.
    When memory_prompt or greeting is edited, the updated memory is stored into Reeve.
    If a public/community persona is edited by a user other than the original creator,
    edits are stored per-user in UserPersonaCustomization so they NEVER overwrite
    the public persona for everyone else.
    """
    permission_classes = [AllowAny]

    def get(self, request, persona_id):
        from .models import Persona, UserPersonaCustomization
        from .serializers import PersonaSerializer

        try:
            persona = Persona.objects.get(id=persona_id)
        except Persona.DoesNotExist:
            return Response({"error": "Persona not found"}, status=status.HTTP_404_NOT_FOUND)

        data = PersonaSerializer(persona).data
        user_id = request.query_params.get("user_id") or (str(request.user.id) if (request.user and request.user.is_authenticated) else None)
        if user_id:
            custom = UserPersonaCustomization.objects.filter(
                user_identifier=str(user_id),
                persona_identifier=str(persona.id),
            ).first()
            if custom:
                if custom.custom_greeting:
                    data["greeting"] = custom.custom_greeting
                if custom.custom_memory_prompt:
                    data["memory_prompt"] = custom.custom_memory_prompt
                if custom.custom_name:
                    data["name"] = custom.custom_name
                if custom.custom_tagline:
                    data["tagline"] = custom.custom_tagline
                data["is_customized_by_user"] = True

        return Response(data, status=status.HTTP_200_OK)

    def patch(self, request, persona_id):
        from .models import Persona, UserPersonaCustomization
        from .serializers import PersonaSerializer
        from .reeve_service import store_memory_for_user

        try:
            persona = Persona.objects.get(id=persona_id)
        except Persona.DoesNotExist:
            return Response({"error": "Persona not found"}, status=status.HTTP_404_NOT_FOUND)

        user_id = (
            str(request.user.id)
            if (request.user and request.user.is_authenticated)
            else (request.data.get("user_id") or request.query_params.get("user_id") or "").strip()
        )
        is_creator = False
        if user_id:
            if persona.creator and str(persona.creator.id) == str(user_id):
                is_creator = True
            elif getattr(persona, "creator_id", None) and str(persona.creator_id) == str(user_id):
                is_creator = True
            elif persona.creator is None:
                # If persona creator was not recorded on creation, treat user as owner
                is_creator = True

        is_public_or_community = bool(persona.is_community or persona.visibility == "public")
        is_public_edit = bool(request.data.get("is_public_edit"))

        # ---------------------------------------------------------------------
        # CASE 1: Explicit edit of the CANONICAL PUBLIC version by the owner
        # This updates the public Persona record in PostgreSQL visible to all users.
        # ---------------------------------------------------------------------
        if is_public_edit:
            if not is_creator and not (request.user and request.user.is_staff):
                return Response(
                    {"error": "Unauthorized: Only the persona creator can edit the public version."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = PersonaSerializer(persona, data=request.data, partial=True)
            if serializer.is_valid():
                updated_persona = serializer.save()

                memory_prompt = request.data.get("memory_prompt")
                greeting = request.data.get("greeting")
                if memory_prompt or greeting:
                    clean_user_id = str(user_id or "creator").strip().replace(":", "_").replace("/", "_")
                    clean_persona_id = str(persona.id).strip().replace(":", "_").replace("/", "_")
                    namespace = f"usr_{clean_user_id}_persona_{clean_persona_id}"
                    user_key = (request.headers.get("X-Memory-User-Key") or request.data.get("user_key") or request.query_params.get("user_key") or "").strip() or None
                    try:
                        summary_text = (
                            f"Persona Profile for {updated_persona.name}: "
                            f"Backstory & Memory: {updated_persona.memory_prompt}. "
                            f"First message script: {updated_persona.greeting}"
                        )
                        store_memory_for_user(summary_text, namespace, user_key=user_key)
                    except Exception:
                        pass

                logger.info("Updated canonical public Persona id=%s by owner user=%s", persona.id, user_id)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ---------------------------------------------------------------------
        # CASE 2: Persona is public/community and user is NOT original creator,
        # isolate the edit strictly to THIS user using UserPersonaCustomization.
        # DO NOT modify the global Persona record for other users!
        # ---------------------------------------------------------------------
        if is_public_or_community and not is_creator:
            clean_user_id = str(user_id or "guest").strip().replace(":", "_").replace("/", "_")
            clean_persona_id = str(persona.id).strip().replace(":", "_").replace("/", "_")
            namespace = f"usr_{clean_user_id}_persona_{clean_persona_id}"
            user_key = (request.headers.get("X-Memory-User-Key") or request.data.get("user_key") or request.query_params.get("user_key") or "").strip() or None

            custom, _ = UserPersonaCustomization.objects.get_or_create(
                user_identifier=str(user_id or "guest"),
                persona_identifier=str(persona.id),
            )
            if "greeting" in request.data:
                custom.custom_greeting = (request.data.get("greeting") or "").strip()
            if "memory_prompt" in request.data:
                custom.custom_memory_prompt = (request.data.get("memory_prompt") or "").strip()
            if "name" in request.data:
                custom.custom_name = (request.data.get("name") or "").strip()
            if "tagline" in request.data:
                custom.custom_tagline = (request.data.get("tagline") or "").strip()
            custom.save()

            eff_name = custom.custom_name or persona.name
            eff_memory = custom.custom_memory_prompt or persona.memory_prompt
            eff_greeting = custom.custom_greeting or persona.greeting

            # Ingest updated memory into Reeve for THIS user's private namespace
            try:
                summary_text = (
                    f"Persona Profile for {eff_name}: "
                    f"Backstory & Memory: {eff_memory}. "
                    f"First message script: {eff_greeting}"
                )
                store_memory_for_user(summary_text, namespace, user_key=user_key)
            except Exception as exc:
                logger.warning("Could not sync Reeve memory for customized persona: %s", exc)

            resp_data = PersonaSerializer(persona).data
            if custom.custom_greeting:
                resp_data["greeting"] = custom.custom_greeting
            if custom.custom_memory_prompt:
                resp_data["memory_prompt"] = custom.custom_memory_prompt
            if custom.custom_name:
                resp_data["name"] = custom.custom_name
            if custom.custom_tagline:
                resp_data["tagline"] = custom.custom_tagline
            resp_data["is_customized_by_user"] = True

            logger.info("Saved user-isolated persona customization for user=%s persona=%s", user_id, persona.id)
            return Response(resp_data, status=status.HTTP_200_OK)

        # ---------------------------------------------------------------------
        # CASE 3: Creator editing their own private persona -> updates base Persona record
        # ---------------------------------------------------------------------
        serializer = PersonaSerializer(persona, data=request.data, partial=True)
        if serializer.is_valid():
            updated_persona = serializer.save()

            memory_prompt = request.data.get("memory_prompt")
            greeting = request.data.get("greeting")
            if memory_prompt or greeting:
                clean_user_id = str(user_id or "guest").strip().replace(":", "_").replace("/", "_")
                clean_persona_id = str(persona.id).strip().replace(":", "_").replace("/", "_")
                namespace = f"usr_{clean_user_id}_persona_{clean_persona_id}"
                user_key = (request.headers.get("X-Memory-User-Key") or request.data.get("user_key") or request.query_params.get("user_key") or "").strip() or None
                try:
                    summary_text = (
                        f"Persona Profile for {updated_persona.name}: "
                        f"Backstory & Memory: {updated_persona.memory_prompt}. "
                        f"First message script: {updated_persona.greeting}"
                    )
                    store_memory_for_user(summary_text, namespace, user_key=user_key)
                except Exception as exc:
                    pass

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, persona_id):
        return self.patch(request, persona_id)

    def delete(self, request, persona_id):
        from .models import Persona

        try:
            persona = Persona.objects.get(id=persona_id)
            persona.delete()
            return Response({"message": "Persona deleted successfully"}, status=status.HTTP_200_OK)
        except Persona.DoesNotExist:
            return Response({"error": "Persona not found"}, status=status.HTTP_404_NOT_FOUND)


class MemoryKeyBackupView(APIView):
    """
    Zero-Knowledge Encrypted Key Backup endpoint.
    The server stores ONLY the encrypted blob, salt, and nonce.
    It NEVER receives or stores the plaintext 256-bit key or the user's 12-word recovery phrase.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        user_identifier = (
            str(request.user.id)
            if (request.user and request.user.is_authenticated)
            else (request.query_params.get("user_id") or request.headers.get("X-User-Id", "")).strip()
        )
        if not user_identifier:
            return Response({"error": "User identifier required"}, status=status.HTTP_400_BAD_REQUEST)

        from .models import UserMemoryKeyBackup
        backup = UserMemoryKeyBackup.objects.filter(user_identifier=user_identifier).first()
        if not backup:
            return Response({"has_backup": False}, status=status.HTTP_200_OK)

        return Response({
            "has_backup": True,
            "encrypted_blob": backup.encrypted_blob,
            "salt": backup.salt,
            "nonce": backup.nonce,
            "updated_at": backup.updated_at.isoformat(),
        }, status=status.HTTP_200_OK)

    def post(self, request):
        user_identifier = (
            str(request.user.id)
            if (request.user and request.user.is_authenticated)
            else (request.data.get("user_id") or request.headers.get("X-User-Id", "")).strip()
        )
        if not user_identifier:
            return Response({"error": "User identifier required"}, status=status.HTTP_400_BAD_REQUEST)

        encrypted_blob = request.data.get("encrypted_blob", "").strip()
        salt = request.data.get("salt", "").strip()
        nonce = request.data.get("nonce", "").strip()

        if not encrypted_blob or not salt or not nonce:
            return Response(
                {"error": "encrypted_blob, salt, and nonce are all required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_obj = request.user if (request.user and request.user.is_authenticated) else None
        if not user_obj and user_identifier != "guest":
            try:
                from authentication.models import User
                user_obj = User.objects.filter(id=user_identifier).first()
            except Exception:
                pass

        from .models import UserMemoryKeyBackup
        backup, created = UserMemoryKeyBackup.objects.update_or_create(
            user_identifier=user_identifier,
            defaults={
                "user": user_obj,
                "encrypted_blob": encrypted_blob,
                "salt": salt,
                "nonce": nonce,
            },
        )
        return Response({
            "success": True,
            "message": "Zero-knowledge memory key backup saved securely.",
            "updated_at": backup.updated_at.isoformat(),
        }, status=status.HTTP_200_OK)


class UserConversationsListView(APIView):
    """
    Returns list of all active conversations for the authenticated user (or specified user_id).
    Each entry includes:
    - persona: PersonaItem representation
    - last_message: { id, sender, text (decrypted), created_at }
    Sorted by last_message.created_at descending.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        user_id = (
            str(request.user.id)
            if (request.user and request.user.is_authenticated)
            else (request.query_params.get("user_id") or request.headers.get("X-User-Id") or "").strip()
        )
        user_key = (request.headers.get("X-Memory-User-Key") or request.query_params.get("user_key") or "").strip() or None

        if not user_id:
            return Response({"conversations": []}, status=status.HTTP_200_OK)

        import uuid
        from django.db.models import Max
        from .models import PersonaChatMessage, Persona
        from .crypto import decrypt_chat_message

        # Find distinct persona identifiers with messages involving this user
        persona_latest = (
            PersonaChatMessage.objects.filter(user_identifier=user_id)
            .values("persona_identifier")
            .annotate(max_created_at=Max("created_at"))
            .order_by("-max_created_at")
        )

        conversations = []
        for row in persona_latest:
            persona_id = row.get("persona_identifier")
            if not persona_id:
                continue

            latest_msg = (
                PersonaChatMessage.objects.filter(
                    user_identifier=user_id,
                    persona_identifier=persona_id,
                )
                .order_by("-created_at")
                .first()
            )
            if not latest_msg:
                continue

            decrypted_text = decrypt_chat_message(
                latest_msg.text,
                user_id=str(user_id),
                client_key=user_key,
            )

            persona_obj = None
            try:
                uuid.UUID(str(persona_id))
                persona_obj = Persona.objects.filter(id=persona_id).first()
            except (ValueError, TypeError):
                persona_obj = None

            if persona_obj:
                persona_data = {
                    "id": str(persona_obj.id),
                    "name": persona_obj.name,
                    "tagline": persona_obj.tagline or "",
                    "age": persona_obj.age or 21,
                    "border_color": persona_obj.border_color or "#F43F5E",
                    "image_url": persona_obj.image_url or "",
                    "greeting": persona_obj.greeting or "",
                    "memory_prompt": persona_obj.memory_prompt or "",
                    "visibility": persona_obj.visibility,
                    "is_community": persona_obj.is_community,
                    "publisher_name": persona_obj.publisher_name or "Amour Creator",
                    "publisher_handle": persona_obj.publisher_handle or "@creator",
                    "publisher_avatar": persona_obj.publisher_avatar or "",
                    "likes_count": persona_obj.likes_count,
                    "chats_count": persona_obj.chats_count,
                    "created_at": persona_obj.created_at.isoformat() if persona_obj.created_at else "",
                    "updated_at": persona_obj.updated_at.isoformat() if persona_obj.updated_at else "",
                }
            else:
                persona_data = {
                    "id": str(persona_id),
                    "name": "Companion",
                    "tagline": "",
                    "age": 21,
                    "border_color": "#F43F5E",
                    "image_url": "",
                    "greeting": "",
                    "memory_prompt": "",
                    "visibility": "private",
                    "is_community": False,
                    "publisher_name": "Amour Creator",
                    "publisher_handle": "@creator",
                    "publisher_avatar": "",
                    "likes_count": 0,
                    "chats_count": 0,
                    "created_at": "",
                    "updated_at": "",
                }

            conversations.append({
                "persona": persona_data,
                "last_message": {
                    "id": str(latest_msg.id),
                    "sender": latest_msg.sender,
                    "text": decrypted_text,
                    "created_at": latest_msg.created_at.isoformat() if latest_msg.created_at else "",
                },
            })

        return Response({"conversations": conversations}, status=status.HTTP_200_OK)




