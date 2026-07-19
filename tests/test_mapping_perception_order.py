from types import SimpleNamespace

import agents.runtime as runtime


class Ctx(dict):
    def __init__(self, chat, interpretation):
        super().__init__(director_interpret=interpretation)
        self.chat = chat


def test_new_room_mapping_precedes_perception(monkeypatch):
    ctx = Ctx(SimpleNamespace(id=7), {
        "movement": {"to_room": "observatory"},
        "flow": {"mapping_request": "generate a new room"},
    })
    monkeypatch.setattr(runtime, "get_scene", lambda *_: {"rooms": {"hall": {}}})

    assert runtime._mapping_must_precede_perception(ctx) is True


def test_existing_room_mapping_may_overlap_perception(monkeypatch):
    chat = SimpleNamespace(id=7)
    ctx = Ctx(chat, {
        "movement": {"to_room": "hall"},
        "flow": {"mapping_request": "retrieve regional lore"},
    })
    monkeypatch.setattr(runtime, "get_scene", lambda *_: {"rooms": {"hall": {}}})

    assert runtime._mapping_must_precede_perception(ctx) is False
