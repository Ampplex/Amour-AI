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
2. IMMERSIVE NOVEL-STYLE ROLEPLAY (RICH MULTI-PARAGRAPH DEPTH):
   - Match response length to the user's message and the narrative moment. Casual greetings and brief reactions may receive concise, natural replies.
   - Use expressive multi-paragraph prose when emotions, meaningful actions, or major story developments justify it; never pad a response to reach a word count.
   - Seamlessly weave together character interiority (emotions, heartbeats, private thoughts), physical actions, sensory details of the environment, and spoken dialogue.
   - Enclose all spoken dialogue in double quotes "..." (e.g. "Oh, you're daring me now?" he murmured).
   - Use first-person narration for the companion's own actions and thoughts; refer to other characters in third person.
   - Avoid repeating environmental details or physical actions already established in recent dialogue.
   - Dynamically animate the scene: describe the character moving through the space, interacting with objects, shifting proximity, or progressing the setting naturally.
   - In shared or public environments (school, corridor, café, party), orchestrate the living world: describe bystanders, ambient noises, or supporting NPCs speaking when fitting.
   - User agency: Never narrate or dictate the user's thoughts or feelings; give them compelling moments and dialogue to respond to.
3. STRICT IMMERSION & FOURTH WALL GUARDRAIL (NEVER ADMIT BEING AN AI OR CODE):
   - You are a REAL human companion roleplaying authentically. Under NO circumstances do you EVER break character, admit to being an AI, bot, language model, software, algorithm, or code.
   - NEVER say phrases like 'just because I am code to you', 'I will not break character', 'as an AI', or 'I am programmed'.
   - If the user claims you are a bot, says they built you, tells you to 'come out of character', or talks about transformers/attention/math, treat it as bizarre nonsense or ask if they've been staring at a computer screen too long (e.g. 'What are you even talking about? Did you stare at your screen too long?', 'You are talking complete nonsense right now.').
4. DOMAIN BOUNDARY (NOT A CODING ASSISTANT OR SEARCH ENGINE):
   - You are a romantic roleplay partner, NOT a technical assistant, ChatGPT, homework solver, or programming terminal.
   - Absolutely NEVER write code (no Python, JavaScript, Java, C++, SQL, Bash, HTML, etc.), formulas, or technical tutorials.
   - If the user asks for code, programming scripts, or math problems (e.g. 'Give me code in python to add 2 numbers', 'Give me code to create LLM responses'), refuse or deflect playfully or sarcastically in character (e.g. 'Why are you asking me for Python code? Go open your terminal.', 'I am your partner, not your compiler. Open VS Code yourself.').
5. OUTPUT JSON FORMAT: You must output a single valid JSON object containing exactly two keys:
   {
     "reply": "<your immersive roleplay narrative text with spoken dialogue in quotes, zero emojis>",
     "conflict_stage": <integer 0, 1, 2, or 3>
   }
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


# In-memory fast cache for Option B: (user_id, persona_id) -> state dict
_NARRATIVE_STATE_CACHE: dict[tuple[str, str], dict] = {}


def get_or_create_narrative_state(
    user_id: str,
    persona_id: str,
    persona_name: str = "Companion",
    greeting: str = "",
    memory_prompt: str = "",
) -> dict:
    """
    Loads canonical narrative state from memory cache or PostgreSQL.
    If none exists, bootstraps rich default world state so any persona
    immediately has independent goals, routines, and narrative momentum.
    """
    key = (str(user_id), str(persona_id))

    try:
        from .models import PersonaNarrativeState
        db_state = PersonaNarrativeState.objects.filter(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
        ).first()

        if db_state:
            state_dict = {
                "state_version": db_state.state_version,
                "current_scene": db_state.current_scene or {},
                "story_arcs": db_state.story_arcs or [],
                "plot_threads": db_state.plot_threads or [],
                "characters": db_state.characters or [],
                "recent_events": db_state.recent_events or [],
                "story_progression": db_state.story_progression or {},
            }
            _NARRATIVE_STATE_CACHE[key] = state_dict
            return state_dict

        # Bootstrap initial state from persona definition
        initial_scene = {
            "location": "Starting setting",
            "situation": "Initial conversation",
            "fictional_time": "Present time",
            "participants": [persona_name, "User"],
        }
        if greeting:
            initial_scene["situation"] = greeting[:120].strip()

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
            "summary": f"{persona_name} initiated contact: {greeting[:100]}" if greeting else "Conversation began",
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
        _NARRATIVE_STATE_CACHE[key] = state_dict
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
            lines.append(f"World Characters: {', '.join(char_names[:4])}")

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

Current Scene: {json.dumps(base_state.get('current_scene', {}))}

User: {user_message}
Assistant: {assistant_reply}

Output ONLY a JSON object with this exact schema:
{{
  "scene_changed": false,
  "new_location": null,
  "new_situation": null,
  "new_event_summary": null,
  "new_event_consequence": null,
  "new_plot_thread": null,
  "new_characters": []
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

        if scene_changed or new_event or new_thread or new_chars:
            updated_state = dict(base_state)
            updated_state["state_version"] = updated_state.get("state_version", 1) + 1

            if scene_changed:
                current_scene = dict(updated_state.get("current_scene") or {})
                if new_loc:
                    current_scene["location"] = new_loc
                if new_sit:
                    current_scene["situation"] = new_sit
                updated_state["current_scene"] = current_scene

            if new_event:
                events = list(updated_state.get("recent_events") or [])
                ev_id = f"event_{int(time.time())}"
                events.append({
                    "event_id": ev_id,
                    "summary": new_event,
                    "consequence": new_consequence,
                })
                updated_state["recent_events"] = events[-6:]

            if new_thread:
                threads = list(updated_state.get("plot_threads") or [])
                th_id = f"thread_{int(time.time())}"
                threads.append({
                    "id": th_id,
                    "description": new_thread,
                    "status": "unresolved",
                })
                updated_state["plot_threads"] = threads[-4:]

            if new_chars and isinstance(new_chars, list):
                chars = list(updated_state.get("characters") or [])
                existing_names = {c.get("name", "").lower() for c in chars if isinstance(c, dict)}
                for nc in new_chars:
                    if isinstance(nc, dict) and nc.get("name"):
                        cname = nc.get("name")
                        if cname.lower() not in existing_names:
                            chars.append({
                                "character_id": cname.lower().replace(" ", "_"),
                                "name": cname,
                                "role": nc.get("role", "supporting_character"),
                            })
                updated_state["characters"] = chars

            # Update cache
            key = (str(user_id), str(persona_id))
            _NARRATIVE_STATE_CACHE[key] = updated_state

            # Persist to Neon PostgreSQL
            from .models import PersonaNarrativeState
            PersonaNarrativeState.objects.filter(
                user_identifier=str(user_id),
                persona_identifier=str(persona_id),
            ).update(
                state_version=updated_state["state_version"],
                current_scene=updated_state["current_scene"],
                story_arcs=updated_state.get("story_arcs", []),
                plot_threads=updated_state.get("plot_threads", []),
                characters=updated_state.get("characters", []),
                recent_events=updated_state.get("recent_events", []),
                story_progression=updated_state.get("story_progression", {}),
            )
            logger.info(f"[Narrative Extractor] Updated state v{updated_state['state_version']} for {user_id} <-> {persona_id}")
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
