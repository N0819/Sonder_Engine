"""The encoder is told what the engine did with the last beat, as the
Director's authors are.

`engine_notices` are the commit's notes on the last beat -- an attire
coverage nobody stated, a contact moved, a lamp gone out, a silent beat's
warning (`ctx.tell_director`, `commit_common.add_engine_notice`). Lane L7a
of the 2026-11-01 review delivered them to both Director authors' payloads
(`director._engine_notices_shown`, `ENGINE_NOTICES_SHOWN`): 71 of 132 chats
held notices nobody read. The encoder writes the beat's state from the
author's prose, and is the one call that can keep a record the engine
corrected from being written back the old way, so its payload carries them
too -- the same list, and no key when there are none.
"""

from __future__ import annotations

from agents import director_prose


class _Ctx(dict):
    language = "en"

    def __init__(self):
        super().__init__()
        self.warnings = []
        self.chat = {"id": 1}

    def add_warning(self, text):
        self.warnings.append(text)


NOTICES = ["attire: the coat's coverage was never stated; its torso kept",
           "the lamp in the kitchen went out at the beat's end"]


def test_the_encoders_payload_carries_the_notices_the_author_was_given():
    payload = director_prose.encoder_payload(
        _Ctx(), {}, "Mara climbs.", {"engine_notices": list(NOTICES)}, None, {}, [])
    assert payload["engine_notices"] == NOTICES


def test_no_notices_no_key():
    payload = director_prose.encoder_payload(_Ctx(), {}, "Mara climbs.", {}, None, {}, [])
    assert "engine_notices" not in payload
