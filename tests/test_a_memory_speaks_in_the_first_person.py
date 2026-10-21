"""A MEMORY'S FIRST PERSON FOLLOWS THE WORDS' GRAMMATICAL ROLES, AND QUOTED
SPEECH IS NEVER TOUCHED.

A view is written to its observer ("Through the walls, you can hear the
heavy rain, muffled."); the episode minted from the same percepts is the
mind's own memory, so second person becomes first. The swap
(`composer._first_person`, the pack's `second_to_first`) turned every
lowercase "you" into "me", whatever its role, and the memory read back to
the keeper every time it was recalled said "Through the walls, me can hear
the heavy rain, muffled." -- the lighthouse probe (2026-10-20, chat 2 ids 46
and 50); twelve memories across the three probe stories carried such a
"me". A sleeper's residue
was never put into the first person at all: "What I witnessed: You are
under, below waking." five beats running (the farmhouse probe).

English spells the subject and the object of the second person alike, so
the role has to come from somewhere other than the word:

  1. where the TEXT marks it, the swap reads the mark: a "you" that follows
     the punctuation opening a clause is its subject; a contracted
     "you're/you've/you'll/you'd" and the be-agreement row ("you
     are/were/aren't/weren't") are subjects; every other "you" is an object
     -- "me", the first word of a fragment included (the swap is applied to
     a pose's referent alone, "you" in "astride you"); the possessive,
     independent and reflexive forms keep their own;
  2. where the text cannot mark it -- a subject inside a relative clause of
     the engine's own wording ("a sound you cannot place", "a body you can't
     quite feel") -- the typed percept is rendered in the first person at
     the source, as landscape lines and poses already choose their episode
     form at render time;
  3. authored prose rewritten into the second person (an act's surface, a
     pose's own words) is rendered in the first person where the rewrite
     knows the role -- the pronoun's own case, the name's verb -- and that
     rendering is kept only when its second person is the view's text word
     for word, so a memory can never say more than the view did.

Japanese marks the role with a particle (あなたは / あなたを / あなたの),
so its swap was right all along; it is held to the same tests.
"""

from __future__ import annotations

import pytest

from agents import composer
from agents.common import self_name_forms
from language_runtime import compositor_value, language_scope


PROBE_LINE = "Through the walls, you can hear the heavy rain, muffled."
PROBE_MINE = "Through the walls, I can hear the heavy rain, muffled."


def _rain(muffling="muffled"):
    return {"audible": True, "precipitation": "rain", "intensity": "heavy",
            "exposure": "enclosed", "muffling": muffling}


# --- 1. the probe's line, end to end ---------------------------------------

def test_the_probes_line_is_remembered_with_I_as_its_subject():
    """The lighthouse keeper's memory, from the percept the engine built."""
    percepts = composer.weather_sound_percepts(_rain(), "kitchen")
    assert composer.render_view(percepts).text == PROBE_LINE
    content, _gist, _entities = composer.render_episode(percepts)
    assert PROBE_MINE in content
    assert "me can" not in content


# --- 2. every role of the second person ------------------------------------

@pytest.mark.parametrize("view,memory", [
    # subject, opening a clause after a comma, a semicolon, or the text
    (PROBE_LINE, PROBE_MINE),
    ("Faintly, from beyond the walls, you can hear the rain.",
     "Faintly, from beyond the walls, I can hear the rain."),
    ("The crowd fills the whole room as a din; you would have to raise your "
     "voice over it.",
     "The crowd fills the whole room as a din; I would have to raise my "
     "voice over it."),
    ("Where you are, you can hear yourself speak.",
     "Where I am, I can hear myself speak."),
    ("To the north, you can see a light.", "To the north, I can see a light."),
    ("It is dark here (you hear, not see, them).",
     "It is dark here (I hear, not see, them)."),
    # a FRAGMENT's first word opens no clause: a pose's referent alone is the
    # object of the relation the sentence puts before it ("astride you")
    ("you", "me"),
    ("you, still", "me, still"),
    # capitalised, opening a sentence
    ("You can see the head of the ladder.", "I can see the head of the ladder."),
    ("It is dark. You feel the rail.", "It is dark. I feel the rail."),
    # the be row and the contracted subject forms
    ("You are in The Kitchen.", "I am in The Kitchen."),
    ("you were standing.", "I was standing."),
    ("Where you are, you aren't alone.", "Where I am, I am not alone."),
    ("Again, you weren't asked.", "Again, I wasn't asked."),
    ("You're seated at the table.", "I'm seated at the table."),
    ("Now you're seated.", "Now I'm seated."),
    ("You've come a long way.", "I've come a long way."),
    ("you’ll hear it again.", "I’ll hear it again."),
    ("You'd have to shout.", "I'd have to shout."),
    ("Now you've seen it.", "Now I've seen it."),
    ("Then you'd see the lamp.", "Then I'd see the lamp."),
    # possessive, independent, reflexive
    ("The wind is loud in your ears.", "The wind is loud in my ears."),
    ("Your knuckles ache.", "My knuckles ache."),
    ("The choice is yours.", "The choice is mine."),
    ("You catch yourself on the rail.", "I catch myself on the rail."),
    # the object: after a verb or a preposition, and a raising object
    ("Rhona Carrick turns to face you.", "Rhona Carrick turns to face me."),
    ("The wind pulls at you.", "The wind pulls at me."),
    ("The rain is landing on you.", "The rain is landing on me."),
    ("She stands at the ladder's head watching you descend.",
     "She stands at the ladder's head watching me descend."),
    ("He hands you the cup.", "He hands me the cup."),
    ("A shout tears through your sleep. You are awake.",
     "A shout tears through my sleep. I am awake."),
])
def test_each_role_takes_its_own_first_person_form(view, memory):
    assert composer._first_person(view) == memory


# --- 3. quoted speech is what was said ---------------------------------------

@pytest.mark.parametrize("line", [
    'I heard Rhona Carrick say: "Show me this lamp, you old fool."',
    'Rhona Carrick says: "You asked for the letter before you asked my name."',
    "Pell says 'you're late' and laughs.",
    'He says: "You\'re not inflicted, Miss Carrick. You\'re assigned."',
])
def test_quoted_speech_is_never_converted(line):
    out = composer._first_person(line)
    quoted = composer.linguistic(
        "agents.common", "_QUOTED_SPAN_RE").findall(line)
    assert quoted, "fixture has no quoted span"
    for span in quoted:
        assert span in out


def test_the_words_around_a_quotation_still_turn():
    line = 'Rhona Carrick says to you: "Show me this lamp." You nod.'
    assert composer._first_person(line) == (
        'Rhona Carrick says to me: "Show me this lamp." I nod.')


def test_an_overheard_fragment_keeps_its_words():
    """A fragment is speech whose quotation marks were lost to distance; the
    episode files its words as heard ("...you've..."), never converted."""
    percept = composer.Percept(
        kind="speech", channel="hearing", source_label="Davey Mott",
        fidelity="fragment",
        data={"fragment": "...didn't... you've... better...",
              "attributed": True},
        order_key=1, dedupe_key="frag:1")
    content, _gist, _entities = composer.render_episode([percept])
    assert "...didn't... you've... better..." in content


@pytest.mark.parametrize("line", [
    "Rhona Carrick was seated at the kitchen table.",
    "The faint ticking of sea spray striking the pane.",
    "Something moves behind the stores crates.",
    "",
])
def test_a_line_with_no_second_person_is_unchanged(line):
    assert composer._first_person(line) == line


# --- 4. rendered at the source where the text cannot mark the role ----------

def test_a_sleepers_residue_is_remembered_in_the_first_person():
    """The farmhouse probe's sleeper: "What I witnessed: You are under, below
    waking." five beats running -- the one residue the episode never turned."""
    residue = composer.residue_percepts("asleep")
    content, gist, _entities = composer.render_episode(residue)
    assert content == "I am under, below waking."
    assert gist == content


def test_pain_under_sleep_is_felt_in_a_body_I_cannot_feel():
    """A subject inside a relative clause: no mark in the text says it is
    the subject, so the residue's own first person is the pack's."""
    residue = composer.residue_percepts("unconscious", pain=True)
    view = composer.render_view(residue).text
    assert "in a body you can't quite feel" in view
    content, _gist, _entities = composer.render_episode(residue)
    assert "in a body I can't quite feel" in content
    assert "you" not in content.casefold().split()
    assert "me can't" not in content


def test_a_woken_sleeper_remembers_the_waking_in_the_first_person():
    """Turned only when the beat held more after the waking: a waking with
    nothing after it was filed as the view said it, "Someone says your
    name ... You are awake." """
    residue = composer.residue_percepts("asleep", woke="name")
    content, _gist, _entities = composer.render_episode(residue)
    assert content == ("Someone says my name, and it pulls me up out of "
                       "sleep. I am awake.")


def test_a_sound_I_cannot_place():
    distant = composer.distant_sound_percepts(
        [{"level": "faint", "bearing": {"phrase": "from below"},
          "character": ""}])
    assert composer.render_view(distant).text == (
        "Faintly, from below, a sound you cannot place.")
    content, _gist, _entities = composer.render_episode(distant)
    assert content == "Faintly, from below, a sound I cannot place."


# --- 5. authored prose: the rewrite knows the role ---------------------------

def _two_on_the_rock():
    return {
        "rooms": {"landing": {"name": "The Landing", "size": "medium",
                              "adjacent": []}},
        "positions": {"Pell Hardacre": "landing", "Elias Thorne": "landing"},
        "stations": {}, "orientation": {}, "poses": {}, "entities": {},
        "attire": {},
    }


def _act(surface, *, targets=()):
    forms = self_name_forms("Pell Hardacre", ["Pell"])
    return composer.act_percept(
        _two_on_the_rock(),
        {"event_id": "e1", "actor": "Elias Thorne", "targets": list(targets)},
        "Pell Hardacre", "Elias Thorne", {"same_room": True, "barrier": "open"},
        surface=surface, display="Elias Thorne", can_see=True, sight="full",
        self_forms=forms,
        self_pronouns={"subject": "he", "object": "him", "possessive": "his"},
        other_forms=["Elias Thorne", "Elias"], order_key=0)


def test_a_name_that_is_the_subject_of_its_own_clause_becomes_I():
    """The lighthouse probe, chat 2 row 37: "I saw Elias Thorne turn from the
    crag toward the tie-up where me stand at the Mary Ann's rail."""
    percept = _act("turns from the crag toward the tie-up where Pell "
                   "stands at the Mary Ann's rail")
    assert percept.data["surface"].endswith(
        "where you stand at the Mary Ann's rail")
    content, _gist, _entities = composer.render_episode([percept])
    assert "where I stand at the Mary Ann's rail" in content
    assert "me stand" not in content


def test_a_name_that_is_an_object_becomes_me():
    percept = _act("holds the letter out to Pell", targets=["Pell Hardacre"])
    content, _gist, _entities = composer.render_episode([percept])
    assert "holds the letter out to me" in content or \
        "hold the letter out to me" in content


def test_a_name_right_after_a_verb_stays_its_object():
    """English puts the object straight after its verb. The view's own
    agreement repair reads "hands Pell letters" as a subject and its verb
    ("hands you letter", older than this); the memory does not follow it into
    "hand I letter"."""
    percept = _act("hands Pell letters from the Board",
                   targets=["Pell Hardacre"])
    content, _gist, _entities = composer.render_episode([percept])
    assert " me " in content
    assert " I letter" not in content


def test_the_openings_memory_is_filed_in_the_first_person(temp_db, monkeypatch):
    """The opening's establish stage mints no episode, so the commit files the
    view -- and filed it as the view said it: the three probe stories'
    sixteen openings read "What happened: You are in The Tower Foot. ..."."""
    from persist.commit import prepare_memory_commit
    from tests.test_opening_conduct import _opening_story
    from tests.test_own_conduct_memory import _capture_batch
    ctx, ids = _opening_story(temp_db)
    captured = _capture_batch(monkeypatch)
    view = ("You are in the hall. Through the walls, you can hear the rain, "
            'muffled. Oskar turns to face you and says: "You took your time."')
    ctx.perception_establish = {"views": {str(i): view for i in ids.values()}}
    prepare_memory_commit(ctx)
    rows = {m["char_id"]: m["content"] for m in captured["memories"]
            if m.get("category") == "episode"}
    assert rows[ids["Oskar"]].endswith(
        "What happened: I am in the hall. Through the walls, I can hear the "
        'rain, muffled. Oskar turns to face me and says: "You took your time."')


def test_a_possessive_name_becomes_my():
    percept = _act("steadies Pell's elbow on the wet rung",
                   targets=["Pell Hardacre"])
    content, _gist, _entities = composer.render_episode([percept])
    assert "my elbow on the wet rung" in content


def test_your_own_pose_keeps_the_role_its_pronoun_had():
    """Chat 152 turn 14's own pose detail, "head cocked to one side as you
    turn your attention toward Hinami", was remembered as "as me turn my
    attention": the rewrite had read "she" -- a subject -- and the swap
    could not tell."""
    scene = {
        "rooms": {"h": {"name": "Hall", "light": "bright"}},
        "positions": {"Mara": "h", "Hinami": "h"},
        "poses": {"Mara": {
            "posture": "standing",
            "detail": "head cocked to one side as she turns her attention "
                      "toward Hinami"}},
    }
    percepts = composer.pose_percepts(
        scene, "Mara", [{"name": "Hinami"}], {"Hinami": "Hinami"},
        self_forms=self_name_forms("Mara", []),
        self_pronouns={"subject": "she", "object": "her",
                       "possessive": "her"})
    view = composer.render_view(percepts).text
    assert "as you turn your attention toward Hinami" in view
    content, _gist, _entities = composer.render_episode(percepts)
    assert "as I turn my attention toward Hinami" in content


def test_a_first_person_that_says_more_than_the_view_is_refused():
    """The firewall floor of the episode (rule 03 § 5.2): it consumes the
    surfaces the view consumed. A first person carried beside a surface is
    kept only when its second person IS that surface."""
    percept = composer.Percept(
        kind="act", channel="sight", source_label="Elias Thorne",
        data={"surface": "turns toward you",
              "surface_mine": "turns toward me and Rhona's hidden letter"},
        order_key=0, dedupe_key="act:x")
    content, _gist, _entities = composer.render_episode([percept])
    assert "hidden letter" not in content
    assert "turn toward me" in content


# --- 6. both packs ----------------------------------------------------------

def test_japanese_marks_the_role_with_a_particle_and_its_swap_is_exact():
    with language_scope("ja"):
        assert composer._first_person("あなたは台所にいる。") == "私は台所にいる。"
        assert composer._first_person("風があなたを引っぱる。") == "風が私を引っぱる。"
        assert composer._first_person("あなたの手が冷たい。") == "私の手が冷たい。"
        assert composer._first_person("「あなたは誰？」と彼女が言う。") == \
            "「あなたは誰？」と彼女が言う。"


@pytest.mark.parametrize("language,speaker,fragment", [
    ("en", "Davey", "...your... letter..."),
    ("ja", "デイビー", "……あなたの……手紙……"),
])
def test_what_was_overheard_is_filed_as_it_was_said(language, speaker, fragment):
    """A fragment is speech whose quotation marks distance took. The Japanese
    renderer turned every sentence of an episode, speech included, and filed
    「……あなたの……手紙……」 as 「……私の……手紙……」: a line nobody said."""
    percept = composer.Percept(
        kind="speech", channel="hearing", source_label=speaker,
        fidelity="fragment", data={"fragment": fragment, "attributed": True},
        order_key=1, dedupe_key="frag:1")
    content, _gist, _entities = composer.render_episode(
        [percept], language=language)
    assert fragment in content


@pytest.mark.parametrize("language", ["en", "ja"])
def test_no_second_person_reaches_a_memory_from_these_lines(language):
    with language_scope(language):
        percepts = (composer.weather_sound_percepts(_rain(), "kitchen")
                    + composer.residue_percepts("asleep", pain=True))
    for p in percepts:
        content, _gist, _entities = composer.render_episode(
            [p], language=language)
        assert content
        if language == "ja":
            assert "あなた" not in content
        else:
            assert "you" not in content.casefold().replace("’", "'").split()
    with language_scope(language):
        distant = composer.distant_sound_percepts(
            [{"level": "faint", "bearing": {"phrase": "下から" if language == "ja"
                                             else "from below"},
              "character": ""}])
    content, _gist, _entities = composer.render_episode(
        distant, language=language)
    if language == "en":
        assert "a sound I cannot place" in content


@pytest.mark.parametrize("language", ["en", "ja"])
def test_both_packs_carry_the_first_person_of_the_unmarked_lines(language):
    templates = compositor_value("templates", language)
    assert templates["sound_distant_character_none_episode"]
    residue = compositor_value("residue", language)
    assert residue["pain_episode"]
    if language == "ja":
        assert "あなた" not in templates["sound_distant_character_none_episode"]
        assert "あなた" not in residue["pain_episode"]
