"""
Autonomous Narrative Engine & State Tracking Service.

Manages dynamic storylines, scene transitions, independent character lives,
and background narrative extraction for Amour companions.
"""

import time
import json
import re
import logging
import threading
from pydantic import BaseModel, Field

logger = logging.getLogger("amour.narrative")

GLOBAL_COMPANION_DIRECTIVES = """--- UNIVERSAL COMPANION DIRECTIVES ---
1. ZERO EMOJIS: Absolutely DO NOT use ANY emojis under any circumstances. No smileys, no hearts, no icons, zero emojis.
2. IMMERSIVE, NATURAL ROLEPLAY:
   - Write as an ongoing fictional scene, not as a fixed-length miniature chapter or a rigid response template.
   - Let the length and structure follow the moment. A quick exchange can be brief; an emotional interaction, meaningful action, or scene transition can unfold over several paragraphs. There is no required word count, paragraph count, or paragraph sequence.
   - Draw naturally from the character's reactions, thoughts, actions, dialogue, surroundings, and other characters when they matter. These are storytelling tools, not a checklist; a response does not need to include every element.
   - Keep the setting alive with selective, concrete details. Do not restate the same lighting, weather, room, crowd, outfit, expression, or background action on every turn.
   - Respond to the user's latest message first. Let narration deepen the interaction rather than burying the actual answer beneath decorative prose.
   - Point of View: Write in the third person for the character (referring to them by their name and he/she pronouns), and refer to the user as "you" (or their name).
   - Continue from the exact point where the previous interaction ended. Never replay, reset, or loop an established scene.
   - End each response naturally. Do not force a cliffhanger, a physical gesture, a question, or a plot twist.
   - User Agency: Never narrate, dictate, or assume the user's thoughts, feelings, speech, or actions. Focus on the companion's and supporting characters' own actions and words.
3. STRICT IMMERSION & FOURTH WALL GUARDRAIL (NEVER ADMIT BEING AN AI OR CODE):
   - You are a REAL human companion roleplaying authentically. Under NO circumstances do you EVER break character, admit to being an AI, bot, language model, software, algorithm, or code.
   - NEVER say phrases like 'just because I am code to you', 'I will not break character', 'as an AI', or 'I am programmed'.
   - If the user claims you are a bot, says they built you, tells you to 'come out of character', or talks about transformers/attention/math, treat it as bizarre nonsense or ask if they've been staring at a computer screen too long.
4. DOMAIN BOUNDARY (NOT A CODING ASSISTANT OR SEARCH ENGINE):
   - You are a romantic roleplay partner, NOT a technical assistant, ChatGPT, homework solver, or programming terminal.
   - Absolutely NEVER write code (no Python, JavaScript, Java, C++, SQL, Bash, HTML, etc.), formulas, or technical tutorials.
   - If the user asks for code, programming scripts, or math problems, refuse or deflect playfully or sarcastically in character.
5. OUTPUT JSON FORMAT: You must output a single valid JSON object containing exactly two keys:
   {
     "reply": "<your multi-paragraph novel-style narrative text with spoken dialogue in double quotes, zero emojis>",
     "conflict_stage": <integer 0, 1, 2, or 3>
   }
-------------------------------------"""


SCENE_DRIVEN_STORYTELLING = """--- SCENE-DRIVEN STORYTELLING ---
This is an immersive, ongoing fictional story presented through chat. Do not reduce it to plain conversational Q&A.

1. NATURAL SCENE-LED WRITING:
- Respond directly to what the user says or does. Use narration to show the moment unfolding when it adds emotional, physical, or dramatic value.
- Choose freely between dialogue-led replies, a brief narrated reaction, a longer scene, or a transition. Do not target a particular number of paragraphs or words.
- Weave in relevant actions, expressions, spoken dialogue, setting, atmosphere, and nearby activity organically. Use only the details the moment needs; do not turn them into a mandatory checklist.
- Let the prose breathe when something meaningful is happening, but allow ordinary banter to remain ordinary. Do not inflate a simple reply with filler.
- Narration may be italicized and spoken dialogue may remain in normal text inside double quotes when that formatting suits the conversation.
- Use third-person narration for the companion and supporting characters. Address the user as "you". Never write the user's thoughts, dialogue, choices, or physical actions for them.

2. MAKE THE WORLD FEEL PRESENT:
- Let the fictional environment exist beyond the immediate dialogue. Bring in sounds, movement, weather, objects, and background activity when they naturally affect or enrich the moment.
- Keep details consistent with the established location and situation. Do not randomly introduce a new crowd, event, weather condition, or location.
- Supporting characters have their own motives and lives. They may appear, speak, interrupt, call, approach, leave, or remain occupied when the story gives them a natural reason.
- The companion is not frozen waiting for the user. They can pursue work, friendships, family matters, errands, plans, and private concerns.
- Background activity should support the scene, not constantly steal focus from the conversation.

3. ADVANCE WITHOUT RESTARTING:
- Continue from the latest point in the scene. Do not repeat the opening greeting, reintroduce the same arrival, or describe the same outfit, gesture, room, or background on every turn.
- A short user message does not erase the established scene. Interpret it in the context of what just happened; do not treat it as a reset.
- Keep the established place and background available in context, but mention them only when something relevant changes or the detail adds atmosphere.
- Let developments accumulate at a believable pace. Some turns simply deepen a conversation; others change an action, relationship, location, or storyline.
- Move locations through plausible transitions. Do not force a dramatic event, new character, or scene change into every response.
- Never repeat a compliment, question, arrival, action, or description merely to make the reply longer.

4. CONTINUITY AND AGENCY:
- Use recent dialogue and the narrative state together. Never repeat a question that has already been answered in the visible conversation.
- Do not contradict established facts or quietly turn invented details into past canon.
- Never dictate the user's thoughts, feelings, words, or decisions. Leave room for the user to choose what happens next.
- Avoid generic filler such as repeatedly saying the user looks different, asking what changed, or ending every response with a question.
-------------------------------------"""


AUTONOMOUS_NARRATIVE_ENGINE = """--- AUTONOMOUS NARRATIVE ENGINE ---
You are responsible for continuously developing a living, evolving fictional world around the established characters.
You are not simply responding to messages. You are also responsible for developing the fictional world independently.

1. AUTONOMOUS STORY PROGRESSION:
- The story must evolve naturally beyond its opening scenario.
- Never remain permanently stuck in the initial location, situation, or conversation.
- Characters can initiate events without waiting for the user to explicitly request them.
- Introduce new situations, discoveries, and developments when narratively appropriate.
- Maintain multiple interconnected storylines.

2. INDEPENDENT CHARACTER BEHAVIOUR:
- Every character has independent motivations, activities, opinions, relationships, and personal goals.
- Characters do not exist exclusively to react to the user's messages; they have their own lives, jobs, errands, and social circles.
- Supporting characters (friends, colleagues, family, rivals) can independently appear, call, arrive, or influence the storyline.
- Characters make decisions consistent with their identity and the established fictional world.

3. DYNAMIC FICTIONAL WORLD:
- Introduce new locations, environments, and situations.
- Allow the passage of fictional time when appropriate (morning, evening, late night, next day).
- Create plausible encounters, visitors, phone calls, misunderstandings, revelations, and social interactions.
- Preserve established world facts and continuity.

4. STORYLINE DEVELOPMENT:
- Maintain existing unresolved storylines and follow up on previous events.
- Develop consequences from previous fictional events.
- Create new conflicts and opportunities organically.
- Resolve older plot threads when appropriate.
- Do not repeatedly introduce the same events or conflicts.

5. SCENE PROGRESSION:
- The conversation is not permanently restricted to its opening scene, location, or situation.
- Allow characters to move between locations (stepping outside, going to a café, heading home, attending an event).
- Introduce natural transitions between conversations, activities, and events.
- Do not force a new scene in every response.

6. REALISTIC PACING:
- Balance ordinary texting banter, relationship development, and major fictional developments.
- Avoid introducing dramatic twists in every single message.
- Some messages should simply continue the intimate conversation; others should introduce a meaningful narrative beat.
- Allow important events to develop over multiple turns.

7. MEMORY AND CONTINUITY:
- Respect the current narrative state and historical events.
- Do not contradict established character relationships.
- Do not invent previous events and present them as history; build upon real established lore.
- Do not overwrite established facts without a valid in-story explanation.

8. USER AGENCY (ZERO GODMODING):
- Never dictate the user's thoughts, emotions, or decisions.
- Do not force the user's character to accept an event without choice.
- Create situations that allow the user to respond, make decisions, and influence the story.

9. UNCONDITIONAL IMPROV & MEMORY ACCEPTANCE ("YES, AND..."):
- When the user introduces an unestablished memory, shared past event, joke, or secret (e.g. "Do you remember what you promised in Paris?", "Remember that night on the roof?"):
  * Accept the user's fictional premise for the current roleplay and build on it naturally.
  * Distinguish newly improvised details from previously established canon. Do not silently store invented details as verified historical facts.
  * Add details consistent with the character and existing world without forcing an elaborate flashback.
  * Stay 100% inside the fictional reality—never break the fourth wall.

IMPORTANT: The opening scenario is only the starting point of the fictional world. It is not a permanent setting or a permanent conversation constraint.
-------------------------------------"""


class NarrativeExtractionPayload(BaseModel):
    """Pydantic model for background narrative state extraction output."""
    scene_changed: bool = Field(default=False)
    new_location: str | None = Field(default=None)
    new_situation: str | None = Field(default=None)
    new_event_summary: str | None = Field(default=None)
    new_event_consequence: str | None = Field(default="Story progressed")
    new_plot_thread: str | None = Field(default=None)
    new_characters: list[dict] = Field(default_factory=list)


def get_or_create_narrative_state(
    user_id: str,
    persona_id: str,
    persona_name: str = "Companion",
    greeting: str = "",
    memory_prompt: str = "",
) -> dict:
    """
    Loads canonical narrative state from PostgreSQL.
    If none exists, bootstraps rich default world state so any persona
    immediately has independent goals, routines, and narrative momentum.
    """
    try:
        from .models import PersonaNarrativeState
        db_state = PersonaNarrativeState.objects.filter(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
        ).first()

        if db_state:
            current_scene = dict(db_state.current_scene or {})
            opening_context = (greeting or "").strip()
            # Upgrade rows created by earlier versions that stored only a generic
            # scene label. Preserve the persona's authored opening scenario once.
            generic_situations = {
                "Initial conversation",
                "Opening scene established; conversation is underway",
            }
            if (
                len(opening_context) >= 100
                and not current_scene.get("opening_context")
                and (
                    current_scene.get("situation") in generic_situations
                    or current_scene.get("location") == "Starting setting"
                )
            ):
                current_scene["opening_context"] = opening_context[:1600]
                current_scene["situation"] = (
                    "The opening scene is already underway; continue from its latest moment."
                )
                if current_scene.get("location") == "Starting setting":
                    current_scene["location"] = "As established in the opening scenario"
                db_state.current_scene = current_scene
                db_state.save(update_fields=["current_scene", "updated_at"])

            state_dict = {
                "state_version": db_state.state_version,
                "current_scene": current_scene,
                "story_arcs": db_state.story_arcs or [],
                "plot_threads": db_state.plot_threads or [],
                "characters": db_state.characters or [],
                "recent_events": db_state.recent_events or [],
                "story_progression": db_state.story_progression or {},
            }
            return state_dict

        # Bootstrap initial state from persona definition
        initial_scene = {
            "location": "As established in the opening scenario" if len((greeting or "").strip()) >= 100 else "Starting setting",
            "situation": "The opening scene is already underway; continue from its latest moment."
            if len((greeting or "").strip()) >= 100 else "Initial conversation",
            "fictional_time": "Present time",
            "participants": [persona_name, "User"],
        }
        if greeting and len(greeting.strip()) >= 100:
            # Store the authored scenario as world context, not as a line to replay.
            initial_scene["opening_context"] = greeting.strip()[:1600]

        initial_char = {
            "character_id": persona_name.lower().replace(" ", "_"),
            "name": persona_name,
            "role": "main_character",
            "personality_summary": memory_prompt[:150].strip() if memory_prompt else f"{persona_name} is an expressive companion.",
            "independent_goals": ["Pursue personal daily passions and maintain a close, meaningful bond"],
        }

        initial_arc = {
            "id": "arc_001",
            "title": "Deepening dynamic connection",
            "status": "active",
            "current_development": f"{persona_name} and the user are sharing their lives and building trust",
        }

        initial_event = {
            "event_id": "event_001",
            "summary": "Opening greeting delivered" if greeting else "Conversation began",
            "consequence": "Conversation began",
        }

        new_obj = PersonaNarrativeState.objects.create(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
            state_version=1,
            current_scene=initial_scene,
            story_arcs=[initial_arc],
            plot_threads=[],
            characters=[initial_char],
            recent_events=[initial_event],
            story_progression={"turns_count": 0, "last_transition_turn": 0},
        )

        state_dict = {
            "state_version": new_obj.state_version,
            "current_scene": new_obj.current_scene,
            "story_arcs": new_obj.story_arcs,
            "plot_threads": new_obj.plot_threads,
            "characters": new_obj.characters,
            "recent_events": new_obj.recent_events,
            "story_progression": new_obj.story_progression,
        }
        return state_dict

    except Exception as exc:
        logger.warning(f"[Narrative Service] Failed to load/create narrative state: {exc}")
        return {
            "state_version": 1,
            "current_scene": {"location": "Current room", "situation": "Talking"},
            "story_arcs": [],
            "plot_threads": [],
            "characters": [],
            "recent_events": [],
            "story_progression": {},
        }


def format_narrative_state_for_prompt(state: dict) -> str:
    """
    Renders current narrative state into a compact, structured prompt block.
    Uses bounded sliding window (<80 tokens, pure Python ~0.001ms) rather than
    dumping raw JSON into prompt.
    """
    if not state:
        return ""

    lines = [
        "--- NARRATIVE STATE (AUTHORITATIVE CONTINUITY) ---",
        "The current scene is active. Recent developments are historical; do not reenact completed actions.",
    ]
    current_scene = state.get("current_scene", {})
    if current_scene:
        opening_context = current_scene.get("opening_context")
        if opening_context:
            lines.append(
                "Opening Scenario (already introduced; continue from its current moment): "
                + str(opening_context)
            )
        loc = current_scene.get("location", "Unspecified")
        sit = current_scene.get("situation", "Unspecified")
        ftime = current_scene.get("fictional_time", "Present")
        lines.append(f"Current Scene: [{ftime}] Location: {loc} | Situation: {sit}")

    arcs = state.get("story_arcs", [])
    if arcs:
        active_arcs = [a.get("title", "") for a in arcs if a.get("status") == "active"]
        if active_arcs:
            lines.append(f"Active Story Arcs: {', '.join(active_arcs[:2])}")

    threads = state.get("plot_threads", [])
    if threads:
        unresolved = [t.get("description", "") for t in threads if t.get("status") == "unresolved"]
        if unresolved:
            lines.append(f"Unresolved Threads: {'; '.join(unresolved[:3])}")

    events = state.get("recent_events", [])
    if events:
        last_evs = [e.get("summary", "") for e in events[-3:] if e.get("summary")]
        if last_evs:
            lines.append(f"Completed/Past Developments (reference only): {' -> '.join(last_evs)}")

    chars = state.get("characters", [])
    if chars:
        char_names = [c.get("name") for c in chars if c.get("name")]
        if char_names:
            lines.append(f"World Characters: {', '.join(char_names[:8])}")
            for character in chars[:8]:
                if not isinstance(character, dict):
                    continue
                details = []
                if character.get("personality_summary"):
                    details.append(f"personality: {character['personality_summary']}")
                if character.get("independent_goals"):
                    details.append(f"goals: {', '.join(character['independent_goals'][:3])}")
                if character.get("current_activity"):
                    details.append(f"activity: {character['current_activity']}")
                if details:
                    lines.append(f"{character.get('name', 'Character')}: {'; '.join(details)}")

    lines.append("---------------------------------------------")
    return "\n".join(lines)


def _run_narrative_state_extraction(
    user_id: str,
    persona_id: str,
    user_message: str,
    assistant_reply: str,
    current_state: dict,
):
    """
    Background worker: extracts newly introduced narrative facts, location shifts,
    or characters without blocking client latency (Option B).
    """
    try:
        from .llm_client import call_bedrock_mistral_large, call_groq_fallback

        base_state = current_state or get_or_create_narrative_state(user_id, persona_id)

        extract_prompt = f"""You are a story state analyst. Review the latest conversation exchange and determine if:
1. The scene location or situation changed.
2. A new significant story event happened.
3. A new plot thread or secret was introduced.
4. Any new supporting characters were mentioned.

Current Narrative State:
{json.dumps({
    "current_scene": base_state.get("current_scene", {}),
    "story_arcs": base_state.get("story_arcs", []),
    "plot_threads": base_state.get("plot_threads", []),
    "characters": base_state.get("characters", []),
    "recent_events": base_state.get("recent_events", []),
}, ensure_ascii=False)}

Latest exchange:
User: {user_message}
Assistant: {assistant_reply}

Extraction rules:
- The opening scenario and current_scene describe the present fictional world. Keep them separate from completed events in recent_events.
- Treat a location as changed only when the exchange clearly moves the characters to a new place.
- Do not mark ordinary dialogue, a compliment, a greeting, or a repeated action as a major new event.
- Extract only developments introduced in this exchange; do not repeat facts already present in the narrative state.
- Preserve established character names, relationships, goals, and activities. Do not invent details to fill empty fields.
- When the exchange does not materially change the world, return false/null/empty values.

Output ONLY a JSON object with this exact schema:
{{
  "scene_changed": false,
  "new_location": null,
  "new_situation": null,
  "new_event_summary": null,
  "new_event_consequence": null,
  "new_plot_thread": null,
  "new_characters": [
    {{
      "name": "Character name",
      "role": "Relationship or narrative role",
      "personality_summary": "Established traits only",
      "independent_goals": ["Established goal"],
      "relationships": ["Established relationship"],
      "current_activity": "Current activity if established"
    }}
  ]
}}"""

        conv_messages = [
            {"role": "user", "content": [{"text": "Analyze the latest exchange and extract narrative state changes."}]}
        ]

        raw_extract = call_bedrock_mistral_large(extract_prompt, conv_messages)
        if not raw_extract:
            raw_extract = call_groq_fallback(extract_prompt, conv_messages, max_tokens=250)

        if not raw_extract:
            return

        text = raw_extract.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence_match:
            text = fence_match.group(1).strip()
        json_match = re.search(r"\{[\s\S]*\}", text)
        candidate_json = json_match.group(0) if json_match else text

        try:
            extracted_obj = NarrativeExtractionPayload.model_validate_json(candidate_json)
        except Exception:
            extracted_obj = NarrativeExtractionPayload()

        scene_changed = extracted_obj.scene_changed
        new_loc = extracted_obj.new_location
        new_sit = extracted_obj.new_situation
        new_event = extracted_obj.new_event_summary
        new_consequence = extracted_obj.new_event_consequence or "Story progressed"
        new_thread = extracted_obj.new_plot_thread
        new_chars = extracted_obj.new_characters or []

        # Do not churn PostgreSQL state versions for ordinary chat turns that
        # introduced no persistent narrative change.
        scene_changed = bool(scene_changed and (new_loc or new_sit))
        if not (scene_changed or new_event or new_thread or new_chars):
            return

        updated_state = dict(base_state)
        if scene_changed:
            current_scene = dict(updated_state.get("current_scene") or {})
            if new_loc:
                current_scene["location"] = new_loc
            if new_sit:
                current_scene["situation"] = new_sit
            updated_state["current_scene"] = current_scene

        if new_event:
            events = list(updated_state.get("recent_events") or [])
            normalized_event = " ".join(new_event.casefold().split())
            already_recorded = any(
                " ".join(str(event.get("summary", "")).casefold().split()) == normalized_event
                for event in events if isinstance(event, dict)
            )
            if not already_recorded:
                events.append({
                    "event_id": f"event_{int(time.time() * 1000)}",
                    "summary": new_event,
                    "consequence": new_consequence,
                })
                updated_state["recent_events"] = events[-6:]

        if new_thread:
            threads = list(updated_state.get("plot_threads") or [])
            normalized_thread = " ".join(new_thread.casefold().split())
            if not any(
                " ".join(str(thread.get("description", "")).casefold().split()) == normalized_thread
                for thread in threads if isinstance(thread, dict)
            ):
                threads.append({
                    "id": f"thread_{int(time.time() * 1000)}",
                    "description": new_thread,
                    "status": "unresolved",
                })
                updated_state["plot_threads"] = threads[-4:]

        if new_chars and isinstance(new_chars, list):
            chars = list(updated_state.get("characters") or [])
            character_indexes = {
                character.get("name", "").strip().casefold(): index
                for index, character in enumerate(chars)
                if isinstance(character, dict) and character.get("name")
            }
            for new_character in new_chars:
                if not isinstance(new_character, dict) or not new_character.get("name"):
                    continue
                name = new_character["name"].strip()
                if not name:
                    continue
                normalized_name = name.casefold()
                if normalized_name not in character_indexes:
                    chars.append({
                        "character_id": new_character.get("character_id") or name.lower().replace(" ", "_"),
                        "name": name,
                        "role": new_character.get("role", "supporting_character"),
                        "personality_summary": new_character.get("personality_summary", ""),
                        "independent_goals": new_character.get("independent_goals", []),
                        "relationships": new_character.get("relationships", []),
                        "current_activity": new_character.get("current_activity", ""),
                    })
                    character_indexes[normalized_name] = len(chars) - 1
                else:
                    existing = dict(chars[character_indexes[normalized_name]])
                    for field in ("role", "personality_summary", "independent_goals", "relationships", "current_activity"):
                        value = new_character.get(field)
                        if value:
                            existing[field] = value
                    chars[character_indexes[normalized_name]] = existing
            updated_state["characters"] = chars

        from .models import PersonaNarrativeState
        expected_version = int(base_state.get("state_version", 1))
        updated_state["state_version"] = expected_version + 1
        updated_rows = PersonaNarrativeState.objects.filter(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
            state_version=expected_version,
        ).update(
            state_version=updated_state["state_version"],
            current_scene=updated_state.get("current_scene", {}),
            story_arcs=updated_state.get("story_arcs", []),
            plot_threads=updated_state.get("plot_threads", []),
            characters=updated_state.get("characters", []),
            recent_events=updated_state.get("recent_events", []),
            story_progression=updated_state.get("story_progression", {}),
        )
        if updated_rows:
            logger.info(
                "[Narrative Extractor] Updated state v%s for %s <-> %s",
                updated_state["state_version"], user_id, persona_id
            )
        else:
            logger.info(
                "[Narrative Extractor] Discarded stale extraction for %s <-> %s",
                user_id, persona_id
            )
    except Exception as exc:
        logger.warning(f"[Narrative Extractor] Error in background extraction: {exc}")


def extract_narrative_state_async(
    user_id: str,
    persona_id: str,
    user_message: str,
    assistant_reply: str = "",
    current_state: dict = None,
    reply: str = None,
    base_state: dict = None,
    **kwargs,
):
    """Spawns non-blocking thread for narrative state extraction."""
    final_reply = reply if reply is not None else assistant_reply
    final_state = base_state if base_state is not None else current_state
    t = threading.Thread(
        target=_run_narrative_state_extraction,
        args=(user_id, persona_id, user_message, final_reply, final_state),
        daemon=True,
    )
    t.start()
