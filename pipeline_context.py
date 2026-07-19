# pipeline_context.py
"""Typed context object carrying all pipeline state."""

from dataclasses import dataclass, field
from typing import Any, Optional
from db import wget

@dataclass
class ChatData:
    id: int
    name: str
    persona_id: Optional[int]
    lorebook_id: Optional[int]
    scenario: str
    created: float

    @classmethod
    def from_row(cls, row) -> "ChatData":
        return cls(
            id=row["id"], name=row["name"],
            persona_id=row["persona_id"],
            lorebook_id=row["lorebook_id"],
            scenario=row["scenario"] or "",
            created=row["created"],
        )

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        val = getattr(self, key, None)
        return val if val is not None else default

@dataclass
class TurnData:
    id: int
    chat_id: int
    idx: int
    player_input: str
    created: float
    frame_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> "TurnData":
        return cls(
            id=row["id"], chat_id=row["chat_id"],
            idx=row["idx"], player_input=row["player_input"] or "",
            created=row["created"], frame_id=row["frame_id"],
        )

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        val = getattr(self, key, None)
        return val if val is not None else default

@dataclass
class PipelineContext:
    chat: ChatData
    turn: TurnData
    cast: list
    input: str

    director_establish: Optional[dict] = None
    director_interpret: Optional[dict] = None
    mapping_stage: Optional[dict] = None
    mapping_quick: Optional[dict] = None
    perception_establish: Optional[dict] = None
    perception_act: Optional[dict] = None
    director_resolve: Optional[dict] = None
    perception_outcome: Optional[dict] = None
    narrator: Optional[dict] = None
    interaction_loop: Optional[dict] = None
    reaction_loop: Optional[dict] = None

    character_results: dict[int, dict] = field(default_factory=dict)
    reaction_results: dict[int, dict] = field(default_factory=dict)

    # Additional human players declaring in the same beat as the primary
    # player (whose input/room/etc. remain the untouched top-level fields
    # above). Each entry: {"persona_id": int, "name": str, "pronouns": dict,
    # "input": str}. Empty for every single-player chat.
    extra_players: list = field(default_factory=list)
    narrator_extra: Optional[dict] = None

    _player_room: Optional[str] = None
    _books: Optional[list[int]] = None
    _persona: Optional[dict] = None
    _fiction_model: Optional[dict] = None
    _simulation_clock: Optional[dict] = None

    warnings: list[str] = field(default_factory=list)
    _extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default=None):
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
            if key.startswith("_") and key in self._extra:
                return self._extra[key]
            return default
        if key.startswith("character:"):
            cid = int(key.split(":")[1])
            return self.character_results.get(cid, default)
        if key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            return self.reaction_results.get(cid, default)
        return self._extra.get(key, default)

    def __setitem__(self, key: str, value: Any):
        if hasattr(self, key):
            setattr(self, key, value)
        elif key.startswith("character:"):
            cid = int(key.split(":")[1])
            self.character_results[cid] = value
        elif key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            self.reaction_results[cid] = value
        else:
            self._extra[key] = value

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        if key.startswith("character:"):
            cid = int(key.split(":")[1])
            if cid in self.character_results:
                return self.character_results[cid]
        if key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            if cid in self.reaction_results:
                return self.reaction_results[cid]
        if key in self._extra:
            return self._extra[key]
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        if hasattr(self, key) and getattr(self, key) is not None:
            return True
        if key.startswith("character:"):
            cid = int(key.split(":")[1])
            return cid in self.character_results
        if key.startswith("reaction:"):
            cid = int(key.split(":")[1])
            return cid in self.reaction_results
        return key in self._extra

    @property
    def chat_id(self) -> int:
        return self.chat.id

    @property
    def turn_id(self) -> int:
        return self.turn.id

    @property
    def turn_idx(self) -> int:
        return self.turn.idx

    def wget(self, key: str, default=None):
        return wget(self.chat.id, key, default)

    def add_warning(self, msg: str):
        self.warnings.append(msg)