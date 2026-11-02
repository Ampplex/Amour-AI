"""
Comprehensive Account & Memory Data Deletion Service.
Permanently purges all user records and associations across BOTH:
1. PostgreSQL (Neon): User, Tokens, Key Backups, Messages, Relationships, Personas, Likes, Follows
2. Neo4j Memory Graph: Episodes, Entities, States, Actions, Relations, Locations, and Graph User Nodes
"""

import os
import logging
from typing import Any, Dict, Optional
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model

logger = logging.getLogger("amour.deletion")

# Neo4j connection defaults
NEO4J_URI_DEFAULT = "neo4j+s://f955eacf.databases.neo4j.io"
NEO4J_USER_DEFAULT = "neo4j"
NEO4J_PASSWORD_DEFAULT = "jZu1CxE3d_XnnFHBln3epP3U0Mwq-_tTgIs3H5T1jRk"


def wipe_neo4j_user_memories(user_id: str, namespace: str, email: str = "") -> Dict[str, Any]:
    """
    Connects to the Neo4j graph database and completely deletes all memories,
    graph entities, states, actions, relationships, and nodes associated with this user.
    """
    clean_user_id = str(user_id).strip().replace(":", "_").replace("/", "_")
    summary = {
        "neo4j_episodes_deleted": 0,
        "neo4j_entities_deleted": 0,
        "neo4j_locations_deleted": 0,
        "neo4j_other_nodes_deleted": 0,
        "neo4j_error": None,
    }

    # 1. Best-effort write buffer cancellation from threelane_memory
    try:
        from threelane_memory.write_buffer import get_write_buffer
        wb = get_write_buffer()
        wb.discard_speaker(namespace)
        wb.discard_speaker(user_id)
        wb.discard_speaker(clean_user_id)
    except Exception:
        pass

    # 2. Connect to Neo4j driver
    try:
        from neo4j import GraphDatabase

        uri = os.environ.get("NEO4J_URI", NEO4J_URI_DEFAULT)
        user = os.environ.get("NEO4J_USER", NEO4J_USER_DEFAULT)
        password = os.environ.get("NEO4J_PASSWORD", NEO4J_PASSWORD_DEFAULT)

        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Delete Episodes and attached States, Actions, Relations
            ep_res = session.run(
                """
                MATCH (ep:Episode)
                WHERE ep.speaker = $user_id 
                   OR ep.speaker = $namespace 
                   OR ep.speaker STARTS WITH 'usr_' + $clean_user_id + '_'
                   OR ep.speaker STARTS WITH $clean_user_id + '_'
                   OR ep.speaker CONTAINS $clean_user_id
                WITH ep, ep.id as ep_id
                OPTIONAL MATCH (ep)-[:HAS_STATE]->(s:State)
                OPTIONAL MATCH (ep)-[:HAS_ACTION]->(a:Action)
                OPTIONAL MATCH (ep)-[:HAS_RELATION]->(rel:Relation)
                DETACH DELETE s, a, rel, ep
                RETURN count(ep_id) AS cnt
                """,
                user_id=user_id,
                namespace=namespace,
                clean_user_id=clean_user_id,
            )
            summary["neo4j_episodes_deleted"] = ep_res.single()["cnt"] if ep_res else 0

            # Delete Entities and attached States
            ent_res = session.run(
                """
                MATCH (e:Entity)
                WHERE e.speaker = $user_id 
                   OR e.speaker = $namespace 
                   OR e.speaker STARTS WITH 'usr_' + $clean_user_id + '_'
                   OR e.speaker STARTS WITH $clean_user_id + '_'
                   OR e.speaker CONTAINS $clean_user_id
                WITH e, e.name as e_name
                OPTIONAL MATCH (e)<-[:OF_ENTITY]-(s:State)
                DETACH DELETE s, e
                RETURN count(e_name) AS cnt
                """,
                user_id=user_id,
                namespace=namespace,
                clean_user_id=clean_user_id,
            )
            summary["neo4j_entities_deleted"] = ent_res.single()["cnt"] if ent_res else 0

            # Delete Locations
            loc_res = session.run(
                """
                MATCH (l:Location)
                WHERE l.speaker = $user_id 
                   OR l.speaker = $namespace 
                   OR l.speaker STARTS WITH 'usr_' + $clean_user_id + '_'
                   OR l.speaker STARTS WITH $clean_user_id + '_'
                   OR l.speaker CONTAINS $clean_user_id
                WITH l, l.name as l_name
                DETACH DELETE l
                RETURN count(l_name) AS cnt
                """,
                user_id=user_id,
                namespace=namespace,
                clean_user_id=clean_user_id,
            )
            summary["neo4j_locations_deleted"] = loc_res.single()["cnt"] if loc_res else 0

            # Delete any remaining orphaned nodes for this user
            other_res = session.run(
                """
                MATCH (n)
                WHERE n.speaker = $user_id 
                   OR n.speaker = $namespace 
                   OR n.speaker STARTS WITH 'usr_' + $clean_user_id + '_'
                   OR n.speaker STARTS WITH $clean_user_id + '_'
                   OR n.speaker CONTAINS $clean_user_id
                   OR (n:User AND (n.id = $user_id OR n.email = $email))
                WITH n, id(n) as nid
                DETACH DELETE n
                RETURN count(nid) AS cnt
                """,
                user_id=user_id,
                namespace=namespace,
                clean_user_id=clean_user_id,
                email=email,
            )
            summary["neo4j_other_nodes_deleted"] = other_res.single()["cnt"] if other_res else 0

        driver.close()
    except Exception as exc:
        logger.error(f"Failed to wipe Neo4j memories for user {user_id}: {exc}")
        summary["neo4j_error"] = str(exc)

    return summary


def delete_user_account_and_memories(user_or_id_or_email: Any) -> Dict[str, Any]:
    """
    Main deletion pipeline.
    Deletes the target user from:
    1. Neo4j graph database (all memory graph episodes, entities, states, actions, locations).
    2. PostgreSQL relational database (User, tokens, chat messages, relationship states, key backups, personas).
    """
    User = get_user_model()

    if isinstance(user_or_id_or_email, User):
        user = user_or_id_or_email
    else:
        ident = str(user_or_id_or_email).strip()
        user = (
            User.objects.filter(id=ident).first()
            or User.objects.filter(email__iexact=ident).first()
            or User.objects.filter(username__iexact=ident).first()
        )

    if not user:
        raise ValueError(f"User '{user_or_id_or_email}' not found in database.")

    user_id = str(user.id)
    email = user.email or ""
    username = user.username or ""
    namespace = getattr(user, "namespace", user_id) or user_id

    report = {
        "user_id": user_id,
        "email": email,
        "username": username,
        "postgres": {},
        "neo4j": {},
    }

    # Step 1: Wipe Neo4j Memory Graph
    neo4j_summary = wipe_neo4j_user_memories(user_id=user_id, namespace=namespace, email=email)
    report["neo4j"] = neo4j_summary

    # Step 2: Wipe PostgreSQL Relational Records
    with transaction.atomic():
        from authentication.models import EmailVerificationToken
        from memory.models import (
            Persona,
            PersonaLike,
            PublisherFollow,
            PersonaChatMessage,
            PersonaRelationshipState,
            UserMemoryKeyBackup,
        )

        # 1. Verification & Reset Tokens
        del_tokens = EmailVerificationToken.objects.filter(email__iexact=email).delete()
        report["postgres"]["email_tokens_deleted"] = del_tokens[0]

        # 2. Client Key Backups
        del_backups = UserMemoryKeyBackup.objects.filter(
            Q(user=user) | Q(user_identifier=user_id) | Q(user_identifier=email)
        ).delete()
        report["postgres"]["memory_key_backups_deleted"] = del_backups[0]

        # 3. Relationship States
        del_rel = PersonaRelationshipState.objects.filter(
            Q(user_identifier=user_id) | Q(user_identifier=email)
        ).delete()
        report["postgres"]["relationship_states_deleted"] = del_rel[0]

        # 4. Chat Messages
        del_chats = PersonaChatMessage.objects.filter(
            Q(user=user) | Q(user_identifier=user_id) | Q(user_identifier=email)
        ).delete()
        report["postgres"]["chat_messages_deleted"] = del_chats[0]

        # 5. Publisher Follows
        del_follows = PublisherFollow.objects.filter(
            Q(user_identifier=user_id) | Q(user_identifier=email)
        ).delete()
        report["postgres"]["publisher_follows_deleted"] = del_follows[0]

        # 6. Persona Likes
        del_likes = PersonaLike.objects.filter(
            Q(user=user) | Q(user_identifier=user_id) | Q(poster=user) | Q(poster_identifier=user_id)
        ).delete()
        report["postgres"]["persona_likes_deleted"] = del_likes[0]

        # 7. User-created Personas
        del_personas = Persona.objects.filter(creator=user).delete()
        report["postgres"]["personas_deleted"] = del_personas[0]

        # 8. User Account itself
        del_user = user.delete()
        report["postgres"]["user_deleted"] = del_user[0]

    logger.info(f"User {user_id} ({email}) and all graph memories successfully deleted: {report}")
    return report
