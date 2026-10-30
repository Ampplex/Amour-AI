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
)

class ReeveStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        status_data = get_reeve_status()
        return Response(status_data)

class ChatMemoryView(APIView):
    """
    Primary chat endpoint.
    Retrieves or generates an intelligent response while storing the interaction
    into the user's isolated Reeve Neo4j knowledge graph using their unique namespace.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"error": "Message content cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Unique namespace is the user's ID
        user_namespace = request.user.namespace

        try:
            # 1. Store the user statement in their memory graph
            store_memory_for_user(f"User: {message}", user_namespace)

            # 2. Query Reeve memory graph for an intelligent reply
            answer = query_memory_for_user(message, user_namespace)

            # 3. Store AI reply into memory graph
            if answer:
                store_memory_for_user(f"Amour AI: {answer}", user_namespace)

            return Response(
                {
                    "reply": answer or "I have committed that to your private memory graph.",
                    "namespace": user_namespace,
                    "user_id": request.user.id,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": f"Memory engine error: {str(e)}"},
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


