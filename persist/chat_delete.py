"""One complete deletion boundary for story-owned persistent state."""

from __future__ import annotations

from core.db import q, qi, transaction


def delete_chat_data(chat_id: int) -> None:
    """Delete one story and every row whose lifetime is owned by it.

    Callers decide whether deletion is authorized and whether a pipeline is
    idle.  Keeping the actual sweep here lets the ordinary delete route and a
    failed, not-yet-launched greeting use the same table inventory.
    """
    chat_id = int(chat_id)
    with transaction():
        # Cascade through turns -> steps -> variants (steps and variants have
        # no direct chat_id).
        for turn in q("SELECT id FROM turns WHERE chat_id=?", (chat_id,)):
            for step in q(
                    "SELECT id FROM steps WHERE turn_id=?", (turn["id"],)):
                qi("DELETE FROM variants WHERE step_id=?", (step["id"],))
            qi("DELETE FROM steps WHERE turn_id=?", (turn["id"],))

        for table in (
            "turns", "events", "world", "checkpoints",
            "chat_chars", "chat_lorebooks", "chat_personas",
            "chat_char_frames", "turn_player_inputs", "frames",
            "guest_grants", "scheduled_events", "room_registry",
            "world_events", "relationship_events", "world_entities",
            "world_placements", "world_conditions",
            "fiction_worlds", "fiction_locations", "transit_edges",
        ):
            qi(f"DELETE FROM {table} WHERE chat_id=?", (chat_id,))

        # The FTS table stores chat_id as text.
        qi("DELETE FROM memory_retrieval_fts WHERE chat_id=?",
           (str(chat_id),))
        qi("DELETE FROM memories WHERE chat_id=?", (chat_id,))
        qi("DELETE FROM memory_summaries WHERE chat_id=?", (chat_id,))
        qi("DELETE FROM lorebooks WHERE chat_id=?", (chat_id,))
        qi("DELETE FROM chats WHERE id=?", (chat_id,))
