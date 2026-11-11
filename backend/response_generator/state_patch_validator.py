from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from .story_director import (
    CharacterState,
    RelationshipState,
    PlotThread,
    StoryState,
)


class PatchValidationError(ValueError):
    """Raised when an incremental StoryState patch is invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


ROOT_FIELDS = {
    "story_summary",
    "characters",
    "relationships",
    "plot_threads",
    "current_scene",
}

CHARACTER_UPDATE_FIELDS = {
    "current_emotional_state",
    "current_physical_state",
    "current_goal",
    "current_location",
    "important_knowledge",
}

SCENE_SCALAR_FIELDS = {
    "location",
    "time",
    "situation",
    "atmosphere",
}

NEW_CHARACTER_FIELDS = {
    "name",
    "role",
    "current_emotional_state",
    "current_physical_state",
    "current_goal",
    "current_location",
    "important_knowledge",
}


def _fail(path: str, message: str) -> None:
    raise PatchValidationError([f"{path}: {message}"])


def _require_object(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        _fail(path, "must be a JSON object.")
    return value


def normalize_story_state_patch(patch: dict) -> dict:
    """
    Remove top-level sections that explicitly represent no changes.

    Malformed operations, unknown identifiers, invalid values and
    unauthorized changes are still rejected by deterministic validation.
    """
    normalized = deepcopy(_require_object(patch, "state_patch"))
    empty_sections = {
        "characters": {},
        "relationships": [],
        "plot_threads": [],
        "current_scene": {},
    }

    for section, empty_value in empty_sections.items():
        if section in normalized and normalized[section] == empty_value:
            normalized.pop(section)

    return normalized


def _require_keys(
    value: dict,
    path: str,
    required: set[str],
    allowed: set[str] | None = None,
) -> None:
    missing = required - set(value)
    if missing:
        _fail(path, f"missing fields: {sorted(missing)}")

    permitted = allowed if allowed is not None else required
    extra = set(value) - permitted
    if extra:
        _fail(path, f"unsupported fields: {sorted(extra)}")


def _require_string(
    value: Any,
    path: str,
    *,
    allow_empty: bool = True,
) -> str:
    if not isinstance(value, str):
        _fail(path, "must be a string.")
    if not allow_empty and not value.strip():
        _fail(path, "must not be empty.")
    return value


def _require_string_list(
    value: Any,
    path: str,
) -> list[str]:
    if not isinstance(value, list):
        _fail(path, "must be a list of strings.")

    result = [
        _require_string(
            item,
            f"{path}[{index}]",
            allow_empty=False,
        )
        for index, item in enumerate(value)
    ]

    if len(result) != len(set(result)):
        _fail(path, "contains duplicate values.")

    return result


def _validate_model(model, value: dict, path: str):
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        _fail(path, str(exc))


def _get_story_state(
    story_state: StoryState | dict | None,
) -> StoryState | None:
    if story_state is None:
        return None

    if isinstance(story_state, StoryState):
        return story_state

    try:
        return StoryState.model_validate(story_state)
    except ValidationError as exc:
        _fail("story_state", f"canonical state is invalid: {exc}")


def _validate_character_references(
    character_ids: list[str],
    known_character_ids: set[str],
    path: str,
) -> None:
    unknown = set(character_ids) - known_character_ids
    if unknown:
        _fail(path, f"unknown character IDs: {sorted(unknown)}")


def _validate_array_delta(
    delta: Any,
    current_values: list[str],
    path: str,
    *,
    known_character_ids: set[str] | None = None,
) -> None:
    delta = _require_object(delta, path)
    _require_keys(
        delta,
        path,
        required=set(),
        allowed={"add", "remove"},
    )

    if "add" not in delta:
        delta["add"] = []
    if "remove" not in delta:
        delta["remove"] = []

    additions = _require_string_list(delta["add"], f"{path}.add")
    removals = _require_string_list(delta["remove"], f"{path}.remove")

    overlap = set(additions) & set(removals)
    if overlap:
        _fail(
            path,
            f"the same values cannot be added and removed: {sorted(overlap)}",
        )

    current_set = set(current_values)
    # Deduplicate additions that already exist rather than hard-failing
    delta["add"] = [item for item in additions if item not in current_set]
    # Filter removals to only items that actually exist
    delta["remove"] = [item for item in removals if item in current_set]

    if known_character_ids is not None:
        _validate_character_references(
            delta["add"],
            known_character_ids,
            f"{path}.add",
        )


def _validate_character_patches(
    patch: dict,
    state: StoryState,
) -> set[str]:
    if "characters" not in patch:
        return set()

    characters = _require_object(patch["characters"], "characters")
    if not characters:
        _fail("characters", "empty character update section.")

    new_character_ids = set()

    for character_id, changes in characters.items():
        _require_string(
            character_id,
            "characters key",
            allow_empty=False,
        )
        changes = _require_object(
            changes,
            f"characters.{character_id}",
        )
        if not changes:
            _fail(
                f"characters.{character_id}",
                "empty character update.",
            )

        if character_id in state.characters:
            extra = set(changes) - CHARACTER_UPDATE_FIELDS
            if extra:
                _fail(
                    f"characters.{character_id}",
                    f"unsupported or immutable fields: {sorted(extra)}",
                )

            for field, value in changes.items():
                field_path = f"characters.{character_id}.{field}"
                if field == "important_knowledge":
                    _validate_array_delta(
                        value,
                        state.characters[character_id].important_knowledge,
                        field_path,
                    )
                else:
                    _require_string(value, field_path)
            continue

        _require_keys(
            changes,
            f"characters.{character_id}",
            required=NEW_CHARACTER_FIELDS,
        )
        _validate_model(
            CharacterState,
            changes,
            f"characters.{character_id}",
        )
        new_character_ids.add(character_id)

    return new_character_ids


def _relationship_pair(
    characters: Any,
    known_character_ids: set[str],
    path: str,
) -> frozenset[str]:
    character_ids = _require_string_list(characters, path)
    if len(character_ids) < 2:
        _fail(path, "a relationship must involve at least two characters.")

    _validate_character_references(
        character_ids,
        known_character_ids,
        path,
    )
    return frozenset(character_ids)


def _validate_relationship_patches(
    patch: dict,
    state: StoryState,
    known_character_ids: set[str],
) -> None:
    if "relationships" not in patch:
        return

    operations = patch["relationships"]
    if not isinstance(operations, list) or not operations:
        _fail("relationships", "must be a non-empty operation list.")

    existing_by_pair: dict[frozenset[str], list] = {}
    for relationship in state.relationships:
        pair = frozenset(relationship.characters)
        existing_by_pair.setdefault(pair, []).append(relationship)

    seen_pairs = set()

    for index, operation in enumerate(operations):
        path = f"relationships[{index}]"
        operation = _require_object(operation, path)
        op = operation.get("op")

        if op not in {"add", "update", "remove"}:
            _fail(path, "op must be add, update or remove.")

        if op == "add":
            if "value" not in operation and any(k in operation for k in ("characters", "character_ids", "relationship", "current_dynamic")):
                operation["value"] = {
                    k: v for k, v in operation.items() if k != "op"
                }
            _require_keys(operation, path, {"op", "value"})
            value = _require_object(operation["value"], f"{path}.value")
            _require_keys(
                value,
                f"{path}.value",
                {
                    "characters",
                    "relationship",
                    "current_dynamic",
                },
            )
            pair = _relationship_pair(
                value["characters"],
                known_character_ids,
                f"{path}.value.characters",
            )
            if pair in existing_by_pair:
                _fail(path, "relationship already exists.")
            _validate_model(
                RelationshipState,
                value,
                f"{path}.value",
            )
        else:
            _require_keys(
                operation,
                path,
                {"op", "characters"}
                if op == "remove"
                else {"op", "characters", "changes"},
            )
            pair = _relationship_pair(
                operation["characters"],
                known_character_ids,
                f"{path}.characters",
            )
            existing = existing_by_pair.get(pair, [])
            if len(existing) != 1:
                _fail(
                    path,
                    "the targeted relationship must exist exactly once.",
                )

            if op == "update":
                if "changes" not in operation and any(k in operation for k in ("relationship", "current_dynamic")):
                    operation["changes"] = {
                        k: v for k, v in operation.items() if k not in {"op", "characters", "character_ids"}
                    }
                changes = _require_object(
                    operation["changes"],
                    f"{path}.changes",
                )
                allowed = {"relationship", "current_dynamic"}
                _require_keys(
                    changes,
                    f"{path}.changes",
                    required=set(),
                    allowed=allowed,
                )
                if not changes:
                    _fail(path, "relationship update contains no changes.")
                for field, value in changes.items():
                    _require_string(value, f"{path}.changes.{field}")

        if pair in seen_pairs:
            _fail(path, "multiple operations target the same relationship.")
        seen_pairs.add(pair)


def _validate_plot_thread_patches(
    patch: dict,
    state: StoryState,
    known_character_ids: set[str],
) -> None:
    if "plot_threads" not in patch:
        return

    operations = patch["plot_threads"]
    if not isinstance(operations, list) or not operations:
        _fail("plot_threads", "must be a non-empty operation list.")

    existing_by_id = {}
    for thread in state.plot_threads:
        if thread.id in existing_by_id:
            _fail(
                "story_state.plot_threads",
                f"duplicate existing plot-thread ID: {thread.id}",
            )
        existing_by_id[thread.id] = thread

    seen_ids = set()

    for index, operation in enumerate(operations):
        path = f"plot_threads[{index}]"
        operation = _require_object(operation, path)
        op = operation.get("op")

        if op not in {"add", "update", "remove"}:
            _fail(path, "op must be add, update or remove.")

        if op == "add":
            if "value" not in operation and any(k in operation for k in ("id", "description", "status", "involved_characters")):
                operation["value"] = {
                    k: v for k, v in operation.items() if k != "op"
                }
            _require_keys(operation, path, {"op", "value"})
            value = _require_object(operation["value"], f"{path}.value")
            _require_keys(
                value,
                f"{path}.value",
                {
                    "id",
                    "description",
                    "status",
                    "involved_characters",
                },
            )
            thread_id = _require_string(
                value["id"],
                f"{path}.value.id",
                allow_empty=False,
            )
            if thread_id in existing_by_id:
                _fail(path, f"plot thread '{thread_id}' already exists.")

            thread = _validate_model(
                PlotThread,
                value,
                f"{path}.value",
            )
            _validate_character_references(
                thread.involved_characters,
                known_character_ids,
                f"{path}.value.involved_characters",
            )
        else:
            _require_keys(
                operation,
                path,
                {"op", "id"}
                if op == "remove"
                else {"op", "id", "changes"},
            )
            thread_id = _require_string(
                operation["id"],
                f"{path}.id",
                allow_empty=False,
            )
            if thread_id not in existing_by_id:
                _fail(path, f"plot thread '{thread_id}' does not exist.")

            if op == "update":
                if "changes" not in operation and any(k in operation for k in ("description", "status", "involved_characters")):
                    operation["changes"] = {
                        k: v for k, v in operation.items() if k not in {"op", "id"}
                    }
                changes = _require_object(
                    operation["changes"],
                    f"{path}.changes",
                )
                allowed = {
                    "description",
                    "status",
                    "involved_characters",
                }
                _require_keys(
                    changes,
                    f"{path}.changes",
                    required=set(),
                    allowed=allowed,
                )
                if not changes:
                    _fail(path, "plot-thread update contains no changes.")

                for field, value in changes.items():
                    field_path = f"{path}.changes.{field}"
                    if field == "description":
                        _require_string(
                            value,
                            field_path,
                            allow_empty=False,
                        )
                    elif field == "status":
                        if value not in {
                            "active",
                            "resolved",
                            "abandoned",
                        }:
                            _fail(field_path, "invalid plot-thread status.")
                    elif field == "involved_characters":
                        ids = _require_string_list(value, field_path)
                        _validate_character_references(
                            ids,
                            known_character_ids,
                            field_path,
                        )

        if thread_id in seen_ids:
            _fail(path, "multiple operations target the same plot thread.")
        seen_ids.add(thread_id)


def _validate_scene_patch(
    patch: dict,
    state: StoryState,
    known_character_ids: set[str],
) -> None:
    if "current_scene" not in patch:
        return

    scene_patch = _require_object(
        patch["current_scene"],
        "current_scene",
    )
    if not scene_patch:
        _fail("current_scene", "empty scene update.")

    allowed = SCENE_SCALAR_FIELDS | {
        "participants",
        "continuity_details",
    }
    _require_keys(
        scene_patch,
        "current_scene",
        required=set(),
        allowed=allowed,
    )

    for field in SCENE_SCALAR_FIELDS:
        if field in scene_patch:
            _require_string(
                scene_patch[field],
                f"current_scene.{field}",
            )

    if "participants" in scene_patch:
        _validate_array_delta(
            scene_patch["participants"],
            state.current_scene.participants,
            "current_scene.participants",
            known_character_ids=known_character_ids,
        )

    if "continuity_details" in scene_patch:
        _validate_array_delta(
            scene_patch["continuity_details"],
            state.current_scene.continuity_details,
            "current_scene.continuity_details",
        )


def _validate_delta_scope(
    final_delta: dict,
    planner_delta: dict,
    path: str,
) -> None:
    for operation in ("add", "remove"):
        final_values = set(final_delta[operation])
        approved_values = set(planner_delta[operation])
        unauthorized = final_values - approved_values
        if unauthorized:
            _fail(
                f"{path}.{operation}",
                "contains values outside planner-approved scope: "
                f"{sorted(unauthorized)}",
            )


def _operation_identity(section: str, operation: dict):
    op = operation["op"]

    if section == "relationships":
        characters = (
            operation["value"]["characters"]
            if op == "add"
            else operation["characters"]
        )
        return op, frozenset(characters)

    if section == "plot_threads":
        thread_id = (
            operation["value"]["id"]
            if op == "add"
            else operation["id"]
        )
        return op, thread_id

    raise ValueError(f"Unsupported operation section: {section}")


def _validate_operation_scope(
    final_operations: list,
    planner_operations: list,
    section: str,
) -> None:
    planner_by_identity = {
        _operation_identity(section, operation): operation
        for operation in planner_operations
    }

    for index, final_operation in enumerate(final_operations):
        identity = _operation_identity(section, final_operation)
        planner_operation = planner_by_identity.get(identity)
        path = f"{section}[{index}]"

        if planner_operation is None:
            _fail(
                path,
                "operation or target was not approved by Story Director.",
            )

        op = final_operation["op"]

        if op == "update":
            unauthorized = (
                set(final_operation["changes"])
                - set(planner_operation["changes"])
            )
            if unauthorized:
                _fail(
                    path,
                    "updated fields exceed planner-approved scope: "
                    f"{sorted(unauthorized)}",
                )

        elif op == "add":
            final_value = final_operation["value"]
            approved_value = planner_operation["value"]
            unauthorized = set(final_value) - set(approved_value)

            if unauthorized:
                _fail(
                    path,
                    "added fields exceed planner-approved scope: "
                    f"{sorted(unauthorized)}",
                )

            if section == "plot_threads":
                if not set(final_value["involved_characters"]).issubset(
                    set(approved_value["involved_characters"])
                ):
                    _fail(
                        path,
                        "involved characters exceed planner-approved scope.",
                    )


def validate_patch_scope(
    final_patch: dict,
    planner_patch: dict,
) -> None:
    """
    Ensure the writer only refines or narrows the planner-approved patch.

    Values for approved fields may be refined, but new targets, fields,
    entities and operation types are not permitted.
    """
    final_patch = _require_object(final_patch, "final_patch")
    planner_patch = _require_object(planner_patch, "planner_patch")

    extra_sections = set(final_patch) - set(planner_patch)
    if extra_sections:
        _fail(
            "final_patch",
            f"sections were not approved by planner: {sorted(extra_sections)}",
        )

    if "characters" in final_patch:
        final_characters = _require_object(
            final_patch["characters"],
            "final_patch.characters",
        )
        planner_characters = _require_object(
            planner_patch.get("characters", {}),
            "planner_patch.characters",
        )

        for character_id, changes in final_characters.items():
            if character_id not in planner_characters:
                _fail(
                    f"characters.{character_id}",
                    "character was not approved by planner.",
                )

            approved_changes = planner_characters[character_id]
            extra_fields = set(changes) - set(approved_changes)
            if extra_fields:
                _fail(
                    f"characters.{character_id}",
                    "fields exceed planner-approved scope: "
                    f"{sorted(extra_fields)}",
                )

            # A new character's permanent identity cannot be rewritten
            # by the Response Generator.
            for identity_field in ("name", "role"):
                if identity_field in changes and (
                    changes[identity_field]
                    != approved_changes.get(identity_field)
                ):
                    _fail(
                        f"characters.{character_id}.{identity_field}",
                        "new-character identity must match planner approval.",
                    )

            if "important_knowledge" in changes:
                if "important_knowledge" not in approved_changes:
                    _fail(
                        f"characters.{character_id}.important_knowledge",
                        "knowledge changes were not approved by planner.",
                    )

                if "name" in approved_changes:
                    # A new CharacterState contains a complete knowledge list,
                    # not an incremental add/remove delta.
                    final_knowledge = set(changes["important_knowledge"])
                    approved_knowledge = set(
                        approved_changes["important_knowledge"]
                    )
                    if not final_knowledge.issubset(approved_knowledge):
                        _fail(
                            f"characters.{character_id}.important_knowledge",
                            "new-character knowledge exceeds planner-approved scope.",
                        )
                else:
                    _validate_delta_scope(
                        changes["important_knowledge"],
                        approved_changes["important_knowledge"],
                        f"characters.{character_id}.important_knowledge",
                    )

    for section in ("relationships", "plot_threads"):
        if section in final_patch:
            _validate_operation_scope(
                final_patch[section],
                planner_patch.get(section, []),
                section,
            )

    if "current_scene" in final_patch:
        final_scene = _require_object(
            final_patch["current_scene"],
            "final_patch.current_scene",
        )
        approved_scene = _require_object(
            planner_patch.get("current_scene", {}),
            "planner_patch.current_scene",
        )
        extra_fields = set(final_scene) - set(approved_scene)
        if extra_fields:
            _fail(
                "current_scene",
                f"fields exceed planner-approved scope: {sorted(extra_fields)}",
            )

        for field in ("participants", "continuity_details"):
            if field in final_scene:
                if field not in approved_scene:
                    _fail(
                        f"current_scene.{field}",
                        "array changes were not approved by planner.",
                    )
                _validate_delta_scope(
                    final_scene[field],
                    approved_scene[field],
                    f"current_scene.{field}",
                )


def validate_story_state_patch(
    patch: dict,
    story_state: StoryState | dict | None,
    *,
    planner_patch: dict | None = None,
) -> dict:
    """
    Validate an incremental patch without modifying canonical StoryState.

    An empty patch is valid with or without StoryState. A non-empty patch
    requires an initialized canonical state.

    Returns a deep copy of the validated patch, or raises
    PatchValidationError with deterministic diagnostics.
    """
    patch = normalize_story_state_patch(patch)

    if not patch:
        return {}

    state = _get_story_state(story_state)
    if state is None:
        _fail(
            "state_patch",
            "cannot contain changes when StoryState is unavailable.",
        )

    _require_keys(
        patch,
        "state_patch",
        required=set(),
        allowed=ROOT_FIELDS,
    )

    if "story_summary" in patch:
        _require_string(patch["story_summary"], "story_summary")

    new_character_ids = _validate_character_patches(patch, state)
    known_character_ids = set(state.characters) | new_character_ids

    _validate_relationship_patches(
        patch,
        state,
        known_character_ids,
    )
    _validate_plot_thread_patches(
        patch,
        state,
        known_character_ids,
    )
    _validate_scene_patch(
        patch,
        state,
        known_character_ids,
    )

    if planner_patch is not None:
        validate_patch_scope(patch, planner_patch)

    return deepcopy(patch)
