import logging
import time
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
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

        if not persona_id or not user_id:
            return Response(
                {"results": [], "count": 0, "page": 1, "has_more": False},
                status=status.HTTP_200_OK,
            )

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
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = list(qs[start:end])
        paged_items.reverse()

        serializer = PersonaChatMessageSerializer(paged_items, many=True)

        return Response(
            {
                "results": serializer.data,
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "has_more": end < total_count,
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

        user_id = request.user.id if request.user.is_authenticated else request.data.get("user_id", "guest")

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
        if persona_id:
            try:
                from .models import Persona
                from django.db.models import F
                persona_obj = Persona.objects.filter(id=persona_id).first()
                if persona_obj:
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

        # 1. Store user message in PostgreSQL
        try:
            PersonaChatMessage.objects.create(
                user=user_obj,
                user_identifier=str(user_id),
                persona=persona_obj,
                persona_identifier=str(persona_id),
                namespace=namespace,
                sender="user",
                text=message,
                client_message_id=client_message_id,
            )
        except Exception as e:
            logger.warning(f"Could not persist user message to DB: {e}")
        except Exception as e:
            logger.warning(f"Could not persist user message to DB: {e}")

        # 2. Generate companion reply (100% Reeve memory graph storage, recall, and Groq LLM)
        try:
            result = generate_companion_reply(
                message=message,
                namespace=namespace,
                persona_name=persona_name,
                greeting=greeting,
                memory_prompt=memory_prompt,
                client_time=client_time,
                client_timezone=client_timezone,
                user_name=user_name,
            )
            reply_text = result["reply"]

            # 3. Store bot response in PostgreSQL
            try:
                bot_msg_record = PersonaChatMessage.objects.create(
                    user=user_obj,
                    user_identifier=str(user_id),
                    persona=persona_obj,
                    persona_identifier=str(persona_id),
                    namespace=namespace,
                    sender="bot",
                    text=reply_text,
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
    Generates avatar personas, names, markdown greetings, or memories
    using the fast and cost-effective Meta Llama 3.1 8B model via AWS Bedrock.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        import os
        import json
        import re
        import boto3

        field = request.data.get("field", "all")
        avatar_name = request.data.get("name", "")
        tagline = request.data.get("tagline", "")

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

        if field == "name":
            prompt = (
                "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
                "You are an evocative AI avatar character designer. Suggest 1 unique avatar name and short tagline. "
                "Respond ONLY in valid JSON: {\"name\": \"...\", \"tagline\": \"...\"}<|eot_id|>\n"
                "<|start_header_id|>user<|end_header_id|>\n"
                "Give me 1 creative AI avatar name and tagline.<|eot_id|>\n"
                "<|start_header_id|>assistant<|end_header_id|>\n"
            )
        elif field == "greeting":
            prompt = (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
                f"You are the character {avatar_name or 'Aria'} ({tagline or 'AI companion'}). "
                "Write an immersive 1-sentence opening greeting using *markdown actions* (e.g. *smiles warmly*). "
                "Respond ONLY in valid JSON: {\"greeting\": \"*action* dialogue\"}<|eot_id|>\n"
                "<|start_header_id|>user<|end_header_id|>\n"
                "Greet me.<|eot_id|>\n"
                "<|start_header_id|>assistant<|end_header_id|>\n"
            )
        elif field == "memory":
            prompt = (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
                f"Define the core memory profile for character {avatar_name or 'Aria'} ({tagline or 'AI companion'}). "
                "Respond ONLY in valid JSON: {\"memory\": \"Background: ...\\nPersonality: ...\\nInterests: ...\"}<|eot_id|>\n"
                "<|start_header_id|>user<|end_header_id|>\n"
                "Generate memory profile.<|eot_id|>\n"
                "<|start_header_id|>assistant<|end_header_id|>\n"
            )
        else:
            prompt = (
                "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
                "You are a creative character designer. Generate a rich AI avatar profile. "
                "Respond ONLY in valid JSON with keys: name, tagline, greeting, memory. "
                "In greeting use *markdown actions*.<|eot_id|>\n"
                "<|start_header_id|>user<|end_header_id|>\n"
                "Generate a complete avatar profile.<|eot_id|>\n"
                "<|start_header_id|>assistant<|end_header_id|>\n"
            )

        try:
            body = json.dumps({
                "prompt": prompt,
                "max_gen_len": 350,
                "temperature": 0.8,
            })
            resp = client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            raw = json.loads(resp["body"].read())
            gen_text = raw.get("generation", "").strip()

            # Extract JSON block
            json_match = re.search(r"\{.*\}", gen_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return Response(parsed)
            return Response({"raw": gen_text})
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



