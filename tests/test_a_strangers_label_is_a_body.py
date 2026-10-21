"""A stranger's label is a referring expression for a BODY.

Tavern probe, 2026-10-20 (chat 1 turn 2): a generated card whose appearance
summary opened "Forty and weathered by years at sea before the harbour
claimed her" was labelled "the forty" in every view of the player who did
not know her, in the interaction loop ("the forty says: ...") and on the
narrator's page ("At the corner table the forty shifts the tin candle
dish"). The label was cut from a flat word list at a word cap, and the
content word the cap stopped on was an age.

The class: a stranger's label is a noun phrase whose head is the body --
"the woman with the scar", "the man in the grey coat", "the unfamiliar
person" -- never a bare modifier, an age, a number or a sentence fragment.
`language_runtime.referring` states the grammar from the pack's own tables;
`common._summary_label` cuts the label; `composer.assign_stranger_labels`
widens it through the summary's own attached clauses on a collision. The
owner's cards carried the same class: "the lean", "the tall", "the sharp
gaze", "the weathered flight jacket over", "the tall full-figured who moves
like", and collisions widened into "the tall and predatory-graceful at top
human".
"""

from __future__ import annotations

import re

import pytest

from agents import composer
from agents.common import _unknown_actor_label, self_reference_forms
from language_runtime import language_pack, language_scope, referring
from story.character_schema import character_card_warnings

#: The probe card's summary, as the generator wrote it.
PROBE = (
    "Forty and weathered by years at sea before the harbour claimed her. "
    "Lean and angular — the kind of thinness that comes from working "
    "rigging and eating irregular. A thin white scar cuts clean through the "
    "left eyebrow. Dark hair cropped short enough to stay clear of wind and "
    "work. Watchful grey eyes set in a face that gives nothing away. Skin "
    "tanned and roughened by salt wind, hands calloused from rope.")
DAVEY = ("A big man in the way dock work makes a man big — broad through "
         "the shoulders and chest, thick-armed, carrying soft weight at the "
         "belly from ale and long nights.")
CORWIN = ("A man of middling height and unremarkable build, dressed plainly "
          "enough to pass in any common room.")

def _openers():
    """The words that open a phrase, in the pack's own tables: the function
    words a cut leaves dangling (``label_dangling``), the participles that
    introduce a phrase (``linking_participles``) and the conjunctions
    (``_BREATH_CONJUNCTIONS``)."""
    pack = language_pack("en")
    card = pack.card("compositor")
    conj = pack.card("linguistics")["agents.common"]["_BREATH_CONJUNCTIONS"]
    return {str(w).casefold() for w in [*card["label_dangling"],
                                        *card["linking_participles"],
                                        *conj["items"]]}


def _ends_whole(label, summary):
    """The label stops where the SUMMARY stops a phrase -- at its own
    punctuation or before a word that opens a new one -- never inside one
    ("in a white" | "dress shirt") and never on a word that opens one."""
    openers, words = _openers(), label.split()[1:]
    if words[-1].casefold() in openers:
        return False
    tail = " ".join(words[-2:]).casefold()
    text = " ".join(summary.split()).casefold()
    at = text.find(tail)
    if at < 0:
        return True
    rest = text[at + len(tail):]
    if not rest or not rest[0].isspace():
        return True
    following = rest.split()[0].strip(".,;:!?\u2014\u2013-")
    return not following or following in openers


class TestAnAgeIsNeverTheBody:
    def test_the_probe_card_is_not_the_forty(self):
        label = _unknown_actor_label("Isolde Varrow", PROBE,
                                     ["Varrow", "the navigator"])
        assert "forty" not in label
        # An age said WITH a word says the word of the body: coordination
        # joins like with like.
        assert label == "the weathered person"

    def test_an_age_is_passed_over_and_what_it_qualifies_is_kept(self):
        for summary, want in (
                ("Thirty, lean, with a limp.", "the lean person"),
                ("Mid-forties and stooped.", "the stooped person"),
                ("Forty-one and stooped by years at sea.", "the stooped person"),
                ("40, grey-haired, sharp-eyed.",
                 "the grey-haired sharp-eyed person")):
            assert _unknown_actor_label("X", summary) == want, summary
        # ...and an age that is not the head stays where the summary put it:
        # a modifier opening a noun phrase, a compound noun built on a
        # number. Pinned because the first draft of the rule lost both
        # ("the unfamiliar person" for the owner's Garret and Kit Sawyer).
        assert _unknown_actor_label(
            "Garret", "mid-thirties human male of average height and build",
            ["Onlooker"]) == "the mid-thirties human male"
        assert _unknown_actor_label(
            "Kit Sawyer", "A gangly fifteen-year-old with scorched cuffs and "
            "a split lip.") == "the gangly fifteen-year-old with scorched cuffs"

    def test_a_number_is_recognised_from_the_packs_own_words(self):
        for word in ("forty", "Forty", "40", "1.7", "thirty-two",
                     "mid-forties", "40s", "one"):
            assert referring.is_number(word), word
        # A compound that ends on a word has made a noun or a modifier of
        # its number, and the pack's article is never its word for one.
        for word in ("fifteen-year-old", "six-tailed", "one-eyed", "a", "tall"):
            assert not referring.is_number(word), word


class TestNoNounIsTheGenericPersonWithAFeature:
    def test_a_list_with_no_noun_carries_what_it_attached(self):
        assert _unknown_actor_label(
            "X", "Sharp gaze, clean uniform, with a scar through one eyebrow."
        ) == "the unfamiliar person with a scar through one eyebrow"

    def test_a_garment_is_not_the_body(self):
        assert _unknown_actor_label(
            "Kess Vantar", "Weathered flight jacket over a patched pressure "
            "suit, close-cropped dark hair, a scar through one eyebrow from a "
            "salvage accident she doesn't talk about.") == "the unfamiliar person"

    def test_a_run_of_modifiers_hangs_on_the_generic_noun(self):
        assert _unknown_actor_label(
            "Veyla", "Tall and predatory-graceful at the top of the human "
            "range, the kind of body that makes eye contact a gamble."
        ) == "the tall and predatory-graceful person"

    def test_the_recogniser_answers_the_same_question(self):
        for summary in (PROBE, "Sharp gaze, clean uniform.",
                        "Weathered flight jacket over a patched pressure suit."):
            assert not referring.names_a_body(summary), summary
        for summary in (DAVEY, CORWIN, "Voluptuous succubus with lavender skin.",
                        "Tall woman, forty, weathered.", "Forty. A weathered woman."):
            assert referring.names_a_body(summary), summary


class TestALabelEndsOnItsPhrase:
    @pytest.mark.parametrize("summary,want", [
        ("A tall, full-figured woman who moves like she has never once been "
         "in a hurry.", "the tall full-figured woman"),
        ("A tall, spare man who has the look of a sailor.", "the tall spare man"),
        ("A heavyset man with a round, jutting belly that defines his "
         "silhouette.", "the heavyset man"),
        ("A striking succubus with an athletic yet curvaceous build and pale "
         "skin.", "the striking succubus"),
    ])
    def test_a_relative_or_a_cut_promise_ends_the_label(self, summary, want):
        assert _unknown_actor_label("X", summary) == want


class TestTwoStrangersAreToldApartByTheirOwnClauses:
    def test_no_noun_strangers_widen_through_their_features(self):
        labels = composer.assign_stranger_labels([
            ("Ann", "Sharp-eyed and weathered, with a thin white scar through "
                    "the left eyebrow.", []),
            ("Bea", "Sharp-eyed and weathered, with a limp.", [])])
        assert labels == {
            "Ann": "the sharp-eyed and weathered person with a thin white scar "
                   "through the left eyebrow",
            "Bea": "the sharp-eyed and weathered person with a limp"}

    def test_a_widened_label_takes_the_whole_feature(self):
        labels = composer.assign_stranger_labels([
            ("Hinami", "a fox woman with six tails and amber eyes", []),
            ("Kuzunoha", "a fox woman with six tails and a silver collar", [])])
        assert labels == {
            "Hinami": "the fox woman with six tails and amber eyes",
            "Kuzunoha": "the fox woman with six tails and a silver collar"}

    @pytest.mark.parametrize("summary", [
        "A woman in her forties wearing a Starfleet medical uniform, red hair "
        "pinned back.",
        "A heavy-set middle-aged man in a white dress shirt and green slacks.",
        "A tall, powerfully built reptilian-adjacent humanoid in a rigidly "
        "tailored dark-grey military uniform with crimson piping.",
        "A pale, sharp-featured woman with a deceptively soft smile, short "
        "ink-black hair.",
        "A tall, full-figured woman who moves like she has never once been in "
        "a hurry.",
    ])
    def test_every_rung_of_the_ladder_is_a_whole_phrase(self, summary):
        """The owner's forced-collision measurement as a class: the word caps
        cut "the woman in her forties wearing", "the heavy-set middle-aged man
        in a white", "the pale sharp-featured woman with a deceptively"."""
        twin = _unknown_actor_label("Twin", summary)
        labels = composer.assign_stranger_labels([
            ("Body", summary, []), ("Twin", "a " + twin[4:], [])])
        assert labels["Body"] != labels["Twin"]
        assert _ends_whole(labels["Body"], summary), labels["Body"]
        # ...and carries no clause about conduct: "who moves like she" is a
        # sentence, not a description ("the tall full-figured who moves
        # like she" was Mireille's widened label).
        assert not re.search(r"\b(?:who|that|which)\b", labels["Body"]), \
            labels["Body"]

    def test_the_probe_room_reaches_the_view_as_three_bodies(self):
        scene = {"rooms": {"taproom": {"name": "The Taproom", "light": "bright"}},
                 "positions": {name: "taproom" for name in
                               ("Tamsin Reed", "Isolde Varrow", "Davey Mott",
                                "Corwin Ashe")}}
        bodies = [
            {"name": "Isolde Varrow", "appearance": PROBE,
             "aliases": ["Varrow", "the navigator"]},
            {"name": "Davey Mott", "appearance": DAVEY, "aliases": []},
            {"name": "Corwin Ashe", "appearance": CORWIN, "aliases": []}]
        display = composer.observer_display_map(scene, "Tamsin Reed", bodies, {})
        assert display == {"Isolde Varrow": "the weathered person",
                           "Davey Mott": "the big man",
                           "Corwin Ashe": "the man"}
        text = composer.render_view(composer.presence_percepts(
            scene, "Tamsin Reed", bodies, display), mode="character").text
        assert "the forty" not in text.casefold()
        assert "the weathered person" in text.casefold()


class TestJapanese:
    def test_the_label_is_the_first_noun_clause(self):
        with language_scope("ja"):
            assert _unknown_actor_label(
                "リリム", "小柄で肉感的な女性の身体。肩口で遊ぶ黒紫の髪、切れ長の菫色の瞳。"
            ) == "見知らぬ小柄で肉感的な女性の身体"

    def test_an_age_or_an_inflection_is_no_noun(self):
        with language_scope("ja"):
            assert _unknown_actor_label("X", "四十歳。海の女。") == "見知らぬ人物"
            assert _unknown_actor_label("X", "痩せている。") == "見知らぬ人物"

    def test_the_ordinal_is_the_packs(self):
        with language_scope("ja"):
            labels = composer.assign_stranger_labels([
                ("A", "ごく普通の人間の若い女性。", []),
                ("B", "ごく普通の人間の若い女性。", [])])
        assert labels == {"A": "見知らぬごく普通の人間の若い女性",
                          "B": "2番目の見知らぬごく普通の人間の若い女性"}

    def test_a_japanese_card_in_an_english_story_is_still_cut(self):
        assert _unknown_actor_label(
            "リリム", "小柄で肉感的な女性の身体。肩口で遊ぶ黒紫の髪。"
        ) == "the 小柄で肉感的な女性の身体"


class TestTheCardWarning:
    @staticmethod
    def _says_no_body(summary):
        sheet = {"embodiment": {"visible": {"summary": summary}}}
        return any("never says what this body IS" in w
                   for w in character_card_warnings(sheet))

    def test_a_summary_that_names_no_body_is_warned(self):
        assert self._says_no_body(PROBE)
        assert self._says_no_body("Sharp gaze, clean uniform.")
        assert self._says_no_body("四十歳。")
        # ...and nothing else is: a summary that names its body, a Japanese
        # one read head-final, an empty one (defaulted, says nothing).
        assert not self._says_no_body(DAVEY)
        assert not self._says_no_body("A lean woman of forty, weathered by sea.")
        assert not self._says_no_body("海の女。")
        assert not self._says_no_body("")


class TestSelfReference:
    def test_a_feature_noun_is_never_claimed_as_self(self):
        """The short self-form is cut at the label's HEAD noun. A label that
        carries a feature ends on the feature's noun, and claiming "the
        hair" as self-reference would turn every "the hair" in a view into
        "you"."""
        forms = self_reference_forms(
            "X", "An old woman with silver hair and sharp eyes.", [])
        assert "the hair" not in forms
        assert "the old woman with silver hair" in forms
        assert "the apprentice" in self_reference_forms(
            "Corin", "A young smith's apprentice with a borrowed sword.", [])
