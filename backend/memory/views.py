import logging
import time
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
    generate_companion_reply,
)

logger = logging.getLogger(__name__)

class ReeveStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        status_data = get_reeve_status()
        return Response(status_data)

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
                logger.warning(f"Error during client-key handover: {exc}")

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
                        )
                    except Exception as exc:
                        logger.warning(f"Could not ingest initial persona memory into Reeve: {exc}")

                if persona_obj.greeting and persona_obj.greeting.strip():
                    try:
                        from .reeve_service import store_memory_for_user
                        store_memory_for_user(f"Assistant: {persona_obj.greeting.strip()}", namespace)
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
            decrypted_results.append(item_copy)

        from .models import PersonaRelationshipState
        rel_state = PersonaRelationshipState.objects.filter(
            user_identifier=user_id,
            persona_identifier=persona_id,
        ).first()
        current_conflict_stage = rel_state.conflict_stage if rel_state else 0

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
        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"error": "Message content cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_message_id = request.data.get("client_message_id", "").strip()
        persona_id = request.data.get("persona_id", "").strip()
        persona_name = request.data.get("persona_name", "")
        greeting = request.data.get("greeting", "")
        memory_prompt = request.data.get("memory_prompt", "")
        client_time = request.data.get("client_time", "")
        client_timezone = request.data.get("client_timezone", "")
        user_name = request.data.get("user_name", "").strip()
        user_key = (request.headers.get("X-Memory-User-Key") or request.data.get("user_key") or "").strip() or None

        user_id = request.user.id if request.user.is_authenticated else (request.data.get("user_id") or "guest")

        # Resolve user name if not explicitly provided
        if not user_name:
            if request.user.is_authenticated:
                user_name = getattr(request.user, "given_name", "") or getattr(request.user, "name", "")
            elif user_id and user_id != "guest":
                try:
                    from authentication.models import User
                    u = User.objects.filter(id=user_id).first()
                    if u:
                        user_name = u.given_name or (u.name.split()[0] if u.name else "") or u.name
                except Exception:
                    pass

        # Strict isolation: Combine user_id + persona_id into a unique, deterministic Reeve namespace
        clean_user_id = str(user_id).strip().replace(":", "_").replace("/", "_")
        clean_persona_id = str(persona_id).strip().replace(":", "_").replace("/", "_") if persona_id else "default"
        namespace = f"usr_{clean_user_id}_persona_{clean_persona_id}"

        from .models import PersonaChatMessage

        # Root Cause Fix: Client Message ID Idempotency Check
        if client_message_id:
            existing_msg = PersonaChatMessage.objects.filter(
                client_message_id=client_message_id
            ).first()
            if existing_msg:
                logger.info(f"Idempotency hit for client_message_id={client_message_id}")
                bot_reply = PersonaChatMessage.objects.filter(
                    user_identifier=str(user_id),
                    persona_identifier=str(persona_id),
                    sender="bot",
                    created_at__gte=existing_msg.created_at,
                ).order_by("created_at").first()

                if bot_reply:
                    return Response(
                        {
                            "id": str(bot_reply.id),
                            "client_message_id": client_message_id,
                            "reply": bot_reply.text,
                            "context": "",
                            "namespace": namespace,
                            "persona_id": persona_id,
                            "user_id": str(user_id),
                        },
                        status=status.HTTP_200_OK,
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
        from .models import PersonaRelationshipState
        rel_state, _ = PersonaRelationshipState.objects.get_or_create(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
        )
        current_conflict_stage = rel_state.conflict_stage

        # Fetch recent dialogue history (last 6 turns) for fast, low-latency conversation context
        recent_turns_qs = list(
            PersonaChatMessage.objects.filter(
                user_identifier=str(user_id),
                persona_identifier=str(persona_id),
            ).order_by("-created_at")[:6]
        )
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
                logger.warning(f"Error during client-key handover on post: {exc}")

        # 1. Store user message in PostgreSQL (Encrypted with client key if provided, else server shield)
        try:
            encrypted_user_msg = encrypt_chat_message(message, user_id=str(user_id), client_key=user_key)
            PersonaChatMessage.objects.create(
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
        except Exception as e:
            logger.warning(f"Could not persist user message to DB: {e}")

        # 2. Generate companion reply (Reeve memory graph storage, recall, dialogue context, and Groq LLM)
        try:
            result = generate_companion_reply(
                message=message,
                namespace=namespace,
                persona_name=persona_name,
                persona_age=persona_age,
                greeting=greeting,
                memory_prompt=memory_prompt,
                client_time=client_time,
                client_timezone=client_timezone,
                user_name=user_name,
                conversation_history=conversation_history,
                current_conflict_stage=current_conflict_stage,
                user_key=user_key,
            )
            reply_text = result.get("reply", "").strip()
            new_conflict_stage = result.get("conflict_stage", current_conflict_stage)

            # Persist updated conflict stage into PostgreSQL database
            if rel_state.conflict_stage != new_conflict_stage:
                rel_state.conflict_stage = new_conflict_stage
                rel_state.save(update_fields=["conflict_stage", "updated_at"])

            if not reply_text:
                return Response(
                    {"error": "Failed to generate companion reply from model"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            # 3. Store bot response in PostgreSQL (Encrypted with client key if provided, else server shield)
            try:
                encrypted_bot_msg = encrypt_chat_message(reply_text, user_id=str(user_id), client_key=user_key)
                bot_msg_record = PersonaChatMessage.objects.create(
                    user=user_obj,
                    user_identifier=str(user_id),
                    persona=persona_obj,
                    persona_identifier=str(persona_id),
                    namespace=namespace,
                    sender="bot",
                    text=encrypted_bot_msg,
                    conflict_stage=new_conflict_stage,
                )
                bot_msg_id = str(bot_msg_record.id)
            except Exception as e:
                logger.warning(f"Could not persist bot message to DB: {e}")
                bot_msg_id = f"bot-{int(time.time() * 1000)}"

            return Response(
                {
                    "id": bot_msg_id,
                    "client_message_id": client_message_id,
                    "reply": reply_text,
                    "conflict_stage": new_conflict_stage,
                    "conflict_level": new_conflict_stage,
                    "context": result.get("context", ""),
                    "namespace": namespace,
                    "persona_id": persona_id,
                    "user_id": str(user_id),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Companion chat error: {e}")
            return Response(
                {"error": f"Companion chat error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class StoreMemoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"error": "text is required"}, status=status.HTTP_400_BAD_REQUEST)

        res = store_memory_for_user(text, request.user.namespace)
        return Response({"status": "stored", "namespace": request.user.namespace, "result": res})

class QueryMemoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = request.data.get("question", "").strip()
        if not question:
            return Response({"error": "question is required"}, status=status.HTTP_400_BAD_REQUEST)

        answer = query_memory_for_user(question, request.user.namespace)
        context = retrieve_context_for_user(question, request.user.namespace)
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
        from .reeve_service import strip_emojis

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
    """
    permission_classes = [AllowAny]

    def get(self, request, persona_id):
        from .models import Persona
        from .serializers import PersonaSerializer

        try:
            persona = Persona.objects.get(id=persona_id)
            return Response(PersonaSerializer(persona).data)
        except Persona.DoesNotExist:
            return Response({"error": "Persona not found"}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, persona_id):
        from .models import Persona
        from .serializers import PersonaSerializer

        try:
            persona = Persona.objects.get(id=persona_id)
        except Persona.DoesNotExist:
            return Response({"error": "Persona not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PersonaSerializer(persona, data=request.data, partial=True)
        if serializer.is_valid():
            updated_persona = serializer.save()

            # If memory_prompt or greeting was updated, ingest it into Reeve for this user's persona namespace
            memory_prompt = request.data.get("memory_prompt")
            greeting = request.data.get("greeting")
            if memory_prompt or greeting:
                user_id = request.user.id if (request.user and request.user.is_authenticated) else request.data.get("user_id", "guest")
                namespace = f"{user_id}_{persona.id}"
                try:
                    summary_text = (
                        f"Persona Profile for {updated_persona.name}: "
                        f"Backstory & Memory: {updated_persona.memory_prompt}. "
                        f"First message script: {updated_persona.greeting}"
                    )
                    store_memory_for_user(summary_text, namespace)
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





