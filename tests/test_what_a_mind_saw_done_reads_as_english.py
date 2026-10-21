"""WHAT A MIND SAW DONE READS AS ENGLISH: after "I saw X", every verb of X's
own coordinated verb phrases takes the base form.

The episode files a watched act as "I saw {label} {action}{ending}"
(`composer._episode_sentence`, `episode_act`), and only the act's FIRST verb
was turned: the lighthouse probe's keeper filed "I saw Rhona Carrick dig into
her jacket and brings out a sealed letter." and "I saw Rhona Carrick keep the
letter held out and waits." (2026-10-20, chat 2 row 40). The verbs after the
first now turn by the one rule a mind's own attempt is turned by
(`composer._verbs_in_base`):

  * a verb phrase of X's continues only after and/or, then/but/yet or a
    comma -- never inside a clause a subordinating or relative word, or a
    dash, opened for its own subject;
  * nouns, lists of the body's parts, plurals ending a list and absolute
    phrases are left alone; an -s word ending the line after "and" is a verb
    only where what stands before "and" ends a verb phrase (the actor's own
    verb, an object pronoun, a particle);
  * quoted spans stay as said;
  * where the phrase cannot be turned exactly, the line is today's: the
    first verb alone.
"""

from __future__ import annotations

import pytest

from agents import composer
from agents.common import self_name_forms
from persist.commit import _own_sequence_memory


def _saw(surface, label="Rhona Carrick"):
    percept = composer.Percept(
        kind="act", channel="sight", source_label=label,
        data={"surface": surface}, order_key=0, dedupe_key="act:x")
    content, _gist, _entities = composer.render_episode([percept])
    return content


# --- 1. the probe's two lines ---------------------------------------------------

def test_the_probes_lines_take_the_base_form_throughout():
    assert _saw("digs into her jacket and brings out a sealed letter") == (
        "I saw Rhona Carrick dig into her jacket and bring out a sealed letter.")
    assert _saw("keeps the letter held out and waits") == (
        "I saw Rhona Carrick keep the letter held out and wait.")


# --- 2. every verb of the actor's own phrases ------------------------------------

@pytest.mark.parametrize("surface,line", [
    ("lifts the cup to her lips, then sets it down on the boards",
     "I saw Rhona Carrick lift the cup to her lips, then set it down on the "
     "boards."),
    ("pauses and sighs", "I saw Rhona Carrick pause and sigh."),
    ("quivers and trembles, clamping tightly",
     "I saw Rhona Carrick quiver and tremble, clamping tightly."),
    ("turns to her and waits", "I saw Rhona Carrick turn to her and wait."),
    ("sets it down and waits", "I saw Rhona Carrick set it down and wait."),
    # the observer's own first person inside the act
    ("turns to face me and holds out the folded letter toward me",
     "I saw Rhona Carrick turn to face me and hold out the folded letter "
     "toward me."),
    # a capitalised first verb
    ("Takes the letter and tucks it away",
     "I saw Rhona Carrick take the letter and tuck it away."),
    # quoted speech stays as said
    ('mouths "she lies, he knows" at Tamsin and steps back',
     'I saw Rhona Carrick mouth "she lies, he knows" at Tamsin and step back.'),
])
def test_every_verb_of_the_actors_phrases_takes_the_base_form(surface, line):
    assert _saw(surface) == line


@pytest.mark.parametrize("surface,line", [
    # nouns ending a list after "and" (the owner's bank)
    ("flushes visibly red across cheeks and ears",
     "I saw Rhona Carrick flush visibly red across cheeks and ears."),
    ("looks around the room, scanning the corners and shadows",
     "I saw Rhona Carrick look around the room, scanning the corners and "
     "shadows."),
    ("pulls the blanket off her hips and legs, letting it pool",
     "I saw Rhona Carrick pull the blanket off her hips and legs, letting it "
     "pool."),
    # another subject's verbs
    ("braces against the rail as the deck lifts and drops under the swell",
     "I saw Rhona Carrick brace against the rail as the deck lifts and drops "
     "under the swell."),
    ("keeps one hand flat on the table while the other holds the pot",
     "I saw Rhona Carrick keep one hand flat on the table while the other "
     "holds the pot."),
    ("intensifies the rhythm — the tongue presses deeper, then withdraws",
     "I saw Rhona Carrick intensify the rhythm — the tongue presses "
     "deeper, then withdraws."),
    # a participle before "and" ends a phrase inside a noun's as readily
    ("watches a man sitting and others standing",
     "I saw Rhona Carrick watch a man sitting and others standing."),
    # only the first sentence is the phrase "I saw" opens
    ("lowers to one knee. Takes the foot in both hands and presses a kiss to it",
     "I saw Rhona Carrick lower to one knee. Takes the foot in both hands and "
     "presses a kiss to it."),
])
def test_what_is_not_the_actors_verb_is_left_as_written(surface, line):
    assert _saw(surface) == line


def test_a_phrase_that_cannot_be_turned_exactly_keeps_todays_line():
    """A noun before "and" leaves the last word a noun or a verb: the first
    verb alone is turned, as it always was."""
    assert _saw("returns his gaze to the hearth fire and drinks") == (
        "I saw Rhona Carrick return his gaze to the hearth fire and drinks.")


# --- 3. the one rule, on the mind's own act too -----------------------------------

@pytest.mark.parametrize("attempt,did", [
    ("keeps the letter held out and waits",
     "I tried to keep the letter held out and wait."),
    ("pauses and sighs", "I tried to pause and sigh."),
])
def test_the_mind_s_own_act_turns_by_the_same_rule(attempt, did):
    content, _ = _own_sequence_memory(
        [{"type": "action", "subjectless": True, "attempt": attempt}],
        "Rhona Carrick", self_forms=self_name_forms("Rhona Carrick", []),
        pronouns={"subject": "she", "object": "her", "possessive": "her"},
        pronouns_mine=True)
    assert content == did


# --- 4. Japanese ------------------------------------------------------------------

def test_a_japanese_watched_act_is_its_surface_whole():
    """Japanese verbs carry no person; the act is filed as its surface."""
    percept = composer.Percept(
        kind="act", channel="sight", source_label="リナ",
        data={"surface": "封筒を取り出して差し出す"}, order_key=0,
        dedupe_key="act:x")
    content, _gist, _entities = composer.render_episode([percept],
                                                        language="ja")
    assert "封筒を取り出して差し出す" in content
