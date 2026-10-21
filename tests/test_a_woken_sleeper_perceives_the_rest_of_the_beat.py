"""A WOKEN SLEEPER PERCEIVES THE REST OF THE BEAT (DESIGN_SOUND_FIELD.md
§ 17, round 2 lane C, 2026-10-20).

Wave B1 woke a sleeper by sound and told them what woke them and nothing
else: "Someone says your name, and it pulls you up out of sleep. You are
awake." -- no room, no company, not the lines said after it. The rest of
the beat happened while they slept, the note said; but the rest of the
beat after the WAKING did not. Chat 40 turn 11: Tamamo murmured "Good
morning, Hinami." at the nest's side (the name wakes her), then three more
lines, in a lit attic with morning light coming in -- and the woken view
held none of it until the next beat.

The class, a test (or more) each:

  1. from the waking moment on, the woken mind perceives as an awake one:
     the room they wake in, who is there, what is said after the waking
     sound; the waking line itself stays what the residue says of it;
  2. the firewall: nothing from before the waking reaches them -- a line
     said while they slept is not in the view, not in the episode;
  3. the earliest placed waking decides (a shout before a name wakes them
     to the shout, and the name's line is then heard awake, with words);
  4. a waking the beat cannot place -- a sound with no step -- gives the
     standing state alone: who is there, never what was said;
  5. the view and the episode agree, in both packs; the commit still ends
     the sleep (`woken` is unchanged).
"""

from __future__ import annotations

from agents import composer
import agents.perception as perception

from tests.test_a_sleeper_wakes_to_sound import _line, _make_ctx, _outcome


WOKE_NAME = ("Someone says your name, and it pulls you up out of sleep. "
             "You are awake.")
WOKE_SHOUT = "A shout tears through your sleep. You are awake."


def _player_lines(*quotes, target="Dr. Moon"):
    return [{"speaker": "Hinami", "exact_quote": q, "volume": "normal",
             "intended_target": target} for q in quotes]


# --- 1 + 2. the remainder, and the firewall --------------------------------

def test_the_woken_mind_gets_the_room_and_what_followed_and_nothing_before(temp_db):
    """A normal voice five paces off does not wake her; her name does; the
    two lines after it reach her as an awake mind's, and the room and the
    man in it with them. The line before, and the waking line's words, do
    not."""
    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [
        _line("Let her sleep a while yet.", target=None),   # 54 dB: under
        _line("Hinami, the car is here."),                  # the name wakes
        _line("Your coat is on the chair."),                # awake now
        _line("We leave in ten minutes.", target=None),
    ])
    assert out.get("woken") == {"Hinami": {"by": "name"}}
    view = out["views"]["player"]
    assert view.startswith(WOKE_NAME)
    after = view[len(WOKE_NAME):]
    # the remainder: the room they wake in, who is there, what was said
    assert "bedroom" in after
    assert "Dr. Moon" in after
    assert "coat is on the chair" in after
    assert "ten minutes" in after
    # the firewall: nothing from before the waking, and not the waking
    # line's words
    assert "sleep a while" not in view
    assert "car is here" not in view
    # the waking is the beat's, not its background
    first = out["observations"]["player"][0]
    assert first["observed"]["text"] == WOKE_NAME
    assert first["phase"] == "change" and first["channel"] == "interoception"
    # the ledger now holds the room, so the next beat is a delta
    standing = out["composer_ledger"]["player"]["standing"]
    assert any(k.startswith("env:") for k in standing)
    assert not any(k.startswith("residue:") for k in standing)


def test_a_character_woken_remembers_the_rest_and_not_what_came_before(temp_db):
    """The character tier: the woken mind's view and its episode both lead
    with the waking and carry only what followed."""
    ctx, _chat = _make_ctx(temp_db, sleeper="Dr. Moon")
    out = _outcome(ctx, _player_lines(
        "I think he is still out.",            # 54 dB across the room: under
        "Moon, the ward is flooding.",         # his name wakes him
        "Bring the lamp and follow me.",       # awake now
    ))
    assert out.get("woken") == {"Dr. Moon": {"by": "name"}}
    pid = next(k for k in out["views"] if k != "player")
    view = out["views"][pid]
    assert view.startswith(WOKE_NAME)
    assert "Bring the lamp" in view
    assert "still out" not in view and "flooding" not in view
    episode = out["episodes"][pid]
    assert episode.startswith("Someone says my name")
    assert "Bring the lamp" in episode
    assert "still out" not in episode and "flooding" not in episode


# --- 3. the earliest placed waking decides ----------------------------------

def test_the_earliest_waking_decides_and_a_later_name_is_heard_awake(temp_db):
    """A shout at the first line wakes her; her name in the third line is
    then a line heard awake, words and all."""
    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [
        _line("Everyone up, now!", "shout", target=None),
        _line("The water is at the door.", target=None),
        _line("Hinami, take the lamp."),
    ])
    assert out.get("woken") == {"Hinami": {"by": "shout"}}
    view = out["views"]["player"]
    assert view.startswith(WOKE_SHOUT)
    assert "water is at the door" in view
    assert "take the lamp" in view
    assert "Everyone up" not in view


def test_sleep_hears_where_places_the_waking(temp_db):
    """The unit: with an `order`, the earliest placed waking wins, a name
    first at the same place; without one, § 13's answer and no place."""
    ctx, chat_id = _make_ctx(temp_db)
    sc = temp_db.wget(chat_id, "scene")
    lines = [dict(_line("Hinami, wake up.", target=None), speaker_room="room1"),
             dict(_line("Fire!", "shout", target=None), speaker_room="room1")]
    order = lambda kind, record: lines.index(record) if kind == "line" else None
    assert perception._sleep_hears_where(
        ctx, sc, "Hinami", "room1", lines,
        name_forms=composer.own_name_forms("Hinami"), order=order) \
        == ("name", False, 0)
    assert perception._sleep_hears_where(
        ctx, sc, "Hinami", "room1", list(reversed(lines)),
        name_forms=composer.own_name_forms("Hinami"),
        order=lambda kind, record: list(reversed(lines)).index(record)) \
        == ("shout", False, 0)
    assert perception._sleep_hears_where(
        ctx, sc, "Hinami", "room1", lines,
        name_forms=composer.own_name_forms("Hinami")) == ("name", False, None)
    assert perception._sleep_hears(
        ctx, sc, "Hinami", "room1", lines,
        name_forms=composer.own_name_forms("Hinami")) == ("name", False)


# --- 4. an unplaced waking gives the standing state alone ---------------------

def test_a_waking_the_beat_cannot_place_gives_the_room_and_no_words(temp_db):
    """A crash the beat does not tie to a step wakes her (`noise`: 80 dB at
    its cell on the impact ladder, some 65 at her ear five paces off);
    nothing says whether the line said this beat came before or after it,
    so she gets the room and the man in it and not the line."""
    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Mind the step.", target=None)],
                   events=[{"kind": "sound", "room": "room1",
                            "level": "deafening", "source": "Dr. Moon",
                            "detail": "a crash of falling crockery"}])
    assert out.get("woken") == {"Hinami": {"by": "noise"}}
    view = out["views"]["player"]
    assert view.startswith("A noise jolts you out of sleep. You are awake.")
    assert "bedroom" in view and "Dr. Moon" in view
    assert "Mind the step" not in view
    assert "crockery" not in view


# --- 5. both packs, and the commit ------------------------------------------

def test_both_packs_lead_with_the_waking_and_follow_with_the_room():
    residue = composer.residue_percepts("asleep", woke="name")[0]
    room = composer.environment_percept("r", "the bedroom", "", "lit")
    for language, lead in (("en", WOKE_NAME),
                           ("ja", "誰かが自分の名前を口にし、その声に眠りの底から"
                                  "引き上げられる。目が覚めた。")):
        for mode in ("player", "character"):
            view = composer.render_view([residue, room], mode=mode,
                                        language=language)
            assert view.text.startswith(lead)
            assert len(view.text) > len(lead)              # the room follows
            assert room.dedupe_key in view.standing_keys
            assert residue.dedupe_key not in view.standing_keys
        content, _gist, _entities = composer.render_episode(
            [residue, room], language=language)
        assert content and "bedroom" in content or "寝室" in content \
            or room.data["room_name"] in content
    # A sleeper who slept on is told the residue alone, as before.
    under = composer.residue_percepts("asleep")[0]
    view = composer.render_view([under, room], mode="player")
    assert view.text == "You are under, below waking."


def test_the_commit_still_ends_the_sleep(temp_db):
    """The outcome that carries the remainder still hands the commit the
    same `woken` record: the sleep ends, and the view it ended on holds
    the beat's remainder."""
    from persist.commit import commit_world_entities
    from story.scene import awareness_map
    ctx, chat_id = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Hinami, the car is here."),
                         _line("Your coat is on the chair.")])
    assert "coat is on the chair" in out["views"]["player"]
    ctx.perception_outcome = out
    commit_world_entities(ctx, "n1")
    assert "hinami" not in awareness_map(chat_id)
