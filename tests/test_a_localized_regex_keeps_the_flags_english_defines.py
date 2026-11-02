"""A localized regex carries every flag its English counterpart carries.

`project_check.check_language_pack_surfaces` compares a localized regex's
capture-group COUNT with English and nothing about its flags (dressing audit,
"parity"). Four Japanese patterns had dropped flags English sets:

    persist.commit_memory._STATION_POSSESSED_BEFORE   34 -> 32
    story.scene._ABSENCE_RE                            2 -> 0
    story.scene._DANGLING_TAIL_RE                      2 -> 0
    mind.skip_memories._NUMBER_RUN                     2 -> 0

Each is a pure-Japanese pattern today, so the missing IGNORECASE changes no
match yet -- and that is the hazard: the guide asks a pack to keep English's
alternatives for code-switching, and the first English branch added to one of
these would silently be case-sensitive where English is not. A pack may ADD a
flag; it may not drop one.
"""

from __future__ import annotations

import pytest

from language_runtime import installed_language_packs, raw_card


def _regexes(value, path=()):
    if isinstance(value, dict):
        if value.get("$type") == "regex":
            yield ".".join(path), int(value.get("flags") or 0)
            return
        for key, child in value.items():
            yield from _regexes(child, path + (str(key),))


@pytest.mark.parametrize("language_id", sorted(
    pid for pid, pack in installed_language_packs().items()
    if pack.story and pid != "en"))
def test_no_localized_regex_drops_an_english_flag(language_id):
    english = dict(_regexes(raw_card("en", "linguistics")))
    localized = dict(_regexes(raw_card(language_id, "linguistics")))
    dropped = {path: (flags, localized[path])
               for path, flags in english.items()
               if path in localized and flags & ~localized[path]}
    assert not dropped, f"{language_id} dropped English regex flags: {dropped}"
