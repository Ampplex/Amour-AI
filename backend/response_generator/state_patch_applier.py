from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError

from .story_director import StoryState
from .state_patch_validator import (
    PatchValidationError,
    validate_story_state_patch,
)


class StoryStatePatchApplicationError(RuntimeError):
    """Raised when a validated StoryState patch cannot be applied safely."""


def _apply_string_list_delta(
    current_values: list[str],
    delta: dict,
    path: str,
) -> list[str]:
    """
    Apply an explicit add/remove operation to a string list.

    Existing order is preserved. New entries are appended in the
    order supplied by the patch.
    """
    if not isinstance(current_values, list):
        raise StoryStatePatchApplicationError(
            f"{path}: existing value must be a list."
        )

    if not isinstance(delta, dict):
        raise StoryStatePatchApplicationError(
            f"{path}: delta must be an object."
        )

    if set(delta) != {"add", "remove"}:
        raise StoryStatePatchApplicationError(
            f"{path}: delta must contain exactly 'add' and 'remove'."
        )

    removals = set(delta["remove"])
    additions = list(delta["add"])

    updated_values = [
        value for value in current_values
        if value not in removals
    ]
    updated_values.extend(additions)

    return updated_values


def _find_relationship_index(
    relationships: list[dict],
    character_ids: list[str],
) -> int:
    """Find exactly one relationship using an order-independent pair."""
    target_pair = frozenset(character_ids)

    matches = [
        index
        for index, relationship in enumerate(relationships)
        if frozenset(relationship["characters"]) == target_pair
    ]

    if len(matches) != 1:
        raise StoryStatePatchApplicationError(
            "Relationship operation expected exactly one matching "
            f"relationship for {sorted(target_pair)}, found {len(matches)}."
        )

    return matches[0]


def _find_plot_thread_index(
    plot_threads: list[dict],
    thread_id: str,
) -> int:
    """Find exactly one plot thread by its stable ID."""
    matches = [
        index
        for index, thread in enumerate(plot_threads)
        if thread["id"] == thread_id
    ]

    if len(matches) != 1:
        raise StoryStatePatchApplicationError(
            f"Plot thread '{thread_id}' must exist exactly once; "
            f"found {len(matches)} matches."
        )

    return matches[0]


def apply_story_state_patch(
    story_state: StoryState | dict | None,
    patch: dict,
    *,
    planner_patch: dict | None = None,
) -> StoryState | None:
    """
    Apply a validated incremental patch to an isolated StoryState copy.

    The function never mutates the supplied canonical state. It revalidates
    the patch, applies only explicit changes, validates the complete result,
    and returns a new StoryState object.

    An empty patch returns an independent copy of the current state, or None
    when StoryState has not yet been initialized.

    This function does not persist to PostgreSQL or increment revisions.
    """
    try:
        validated_patch = validate_story_state_patch(
            patch=patch,
            story_state=story_state,
            planner_patch=planner_patch,
        )
    except PatchValidationError as exc:
        raise StoryStatePatchApplicationError(
            "StoryState patch failed validation: "
            + "; ".join(exc.errors)
        ) from exc

    if story_state is None:
        return None

    try:
        canonical_state = (
            story_state
            if isinstance(story_state, StoryState)
            else StoryState.model_validate(story_state)
        )
        state_data = deepcopy(canonical_state.model_dump(mode="python"))

        # 1. Characters: create new entities first, then update existing ones.
        existing_character_ids = set(state_data["characters"])

        for character_id, changes in validated_patch.get("characters", {}).items():
            if character_id not in existing_character_ids:
                state_data["characters"][character_id] = deepcopy(changes)
                continue

            character_data = state_data["characters"][character_id]
            for field, value in changes.items():
                if field == "important_knowledge":
                    character_data["important_knowledge"] = _apply_string_list_delta(
                        current_values=character_data["important_knowledge"],
                        delta=value,
                        path=f"characters.{character_id}.important_knowledge",
                    )
                else:
                    character_data[field] = deepcopy(value)

        # 2. Relationships: target existing entries by unordered character IDs.
        relationships = state_data["relationships"]
        for operation in validated_patch.get("relationships", []):
            op = operation["op"]

            if op == "add":
                relationships.append(deepcopy(operation["value"]))
            elif op == "update":
                index = _find_relationship_index(
                    relationships,
                    operation["characters"],
                )
                relationships[index].update(deepcopy(operation["changes"]))
            elif op == "remove":
                index = _find_relationship_index(
                    relationships,
                    operation["characters"],
                )
                del relationships[index]
            else:
                raise StoryStatePatchApplicationError(
                    f"Unsupported relationship operation: {op}"
                )

        # 3. Plot threads: target entries by stable thread ID.
        plot_threads = state_data["plot_threads"]
        for operation in validated_patch.get("plot_threads", []):
            op = operation["op"]

            if op == "add":
                plot_threads.append(deepcopy(operation["value"]))
            elif op == "update":
                index = _find_plot_thread_index(
                    plot_threads,
                    operation["id"],
                )
                plot_threads[index].update(deepcopy(operation["changes"]))
            elif op == "remove":
                index = _find_plot_thread_index(
                    plot_threads,
                    operation["id"],
                )
                del plot_threads[index]
            else:
                raise StoryStatePatchApplicationError(
                    f"Unsupported plot-thread operation: {op}"
                )

        # 4. Current scene: update supplied scalars and explicit list deltas.
        scene_patch = validated_patch.get("current_scene", {})
        current_scene = state_data["current_scene"]

        for field in ("location", "time", "situation", "atmosphere"):
            if field in scene_patch:
                current_scene[field] = deepcopy(scene_patch[field])

        for field in ("participants", "continuity_details"):
            if field in scene_patch:
                current_scene[field] = _apply_string_list_delta(
                    current_values=current_scene[field],
                    delta=scene_patch[field],
                    path=f"current_scene.{field}",
                )

        # 5. Story summary: replace only when explicitly supplied.
        if "story_summary" in validated_patch:
            state_data["story_summary"] = deepcopy(
                validated_patch["story_summary"]
            )

        # 6. Validate the complete snapshot before exposing it to callers.
        return StoryState.model_validate(state_data)

    except StoryStatePatchApplicationError:
        raise
    except ValidationError as exc:
        raise StoryStatePatchApplicationError(
            f"The resulting StoryState failed Pydantic validation: {exc}"
        ) from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise StoryStatePatchApplicationError(
            f"Could not apply StoryState patch: {exc}"
        ) from exc
