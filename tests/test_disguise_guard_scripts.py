"""The disguise guard and the identity strips work in an unspaced script.

Review 2026-09-07 A2: `\\b`, `[a-z]+` and English word tuples sat at the
firewall sites, so a Japanese story got a guard that never fired and a
fallback label in English.
"""
from language_runtime import language_scope

import agents.common as common
import persist.commit as commit_attire
import story.scene as scene


def test_a_kana_term_is_scrubbed_and_the_fallback_label_is_the_packs():
    with language_scope("ja"):
        out = scene.disguised_visible_appearance(
            "六本の金色の尾を持つ女", {"concealed_terms": ["尾"]})
        assert "尾" not in out
        fallback = scene.disguised_visible_appearance(
            "尾", {"concealed_terms": ["尾"]})
        assert fallback == "特徴のない外見の人物"
        # a denial that names the concealed part is dropped, in Japanese
        kept = scene._positive_presented_appearance(
            "普通の旅人。尾は見えない。", ["尾"])
        assert "尾" not in kept and "旅人" in kept


def test_part_tokens_see_inside_an_unspaced_run():
    assert {"尾", "耳"} <= scene._part_tokens("尾と耳")
    assert scene._part_tokens("尾") <= scene._part_tokens("尾と耳")
    assert not (scene._part_tokens("角") <= scene._part_tokens("尾と耳"))


def test_the_identity_strip_takes_the_particle_with_the_name():
    with language_scope("ja"):
        assert common._strip_identity_tokens("ヒナミは狐の耳を持つ", ["ヒナミ"]) \
            == "狐の耳を持つ"
    assert common._strip_identity_tokens("Hinami's fox ears", ["Hinami"]) == "fox ears"
    assert common._strip_identity_tokens("Hinamis", ["Hinami"]) == "Hinamis", \
        "a Latin name still refuses to match inside a longer word"


def test_a_kana_garment_licenses_its_own_note():
    assert commit_attire._garment_named_in("彼女は上着を脱いだ", "上着")
    assert commit_attire._garment_named_in("the hem of your shift", "linen shift")
    assert not commit_attire._garment_named_in("a bare hand", "cap")


def test_a_quoted_line_is_counted_in_its_own_script():
    """A2: `[A-Za-z']+` measured 0 words in Japanese prose, so every quoted
    span fell under `_PROSE_QUOTE_MIN_WORDS` and the prose-quote authority
    floor -- the one that catches a line nobody declared -- never fired. The
    ja pack's `_PROSE_QUOTE_RES` did not know 「」 either, while every other
    quote value in the same section did."""
    assert common._countable_word_units("I'm not sure about that") == 5
    assert common._countable_word_units("本当にいいのか") == 7
    with language_scope("ja"):
        flagged = common._check_prose_quote_authority(
            "彼女は「本当にいいのか」と言った。", [])
        assert flagged and "本当にいいのか" in flagged[0]
        assert common._check_prose_quote_authority(
            "彼女は「本当にいいのか」と言った。", ["本当にいいのか"]) == []
        # A label is still a label: two characters is under the floor.
        assert common._check_prose_quote_authority(
            "看板には「安全」とある。", []) == []


def test_phrase_and_shingle_tokens_exist_in_an_unspaced_script():
    """A2: the tic report split on `[^A-Za-z']+` and the recycled-prose
    shingles matched `[a-z0-9']+`, so a Japanese sentence produced no
    phrases at all and one shingle token per clause. Latin prose tokenises
    exactly as before -- checked against 24 MB of stored prose, 0 diffs."""
    assert common._phrase_segments("She walked, then stopped.") == [
        ["She", "walked"], ["then", "stopped"]]
    assert common._phrase_segments("雨が静かに降り、街は眠る。") == [
        list("雨が静かに降り"), list("街は眠る")]
    assert common._word_shingles(
        "the rain kept falling on the quiet empty street") \
        == {"rain kept falling quiet empty street"}
    assert common._word_shingles("雨が静かに降り続けている夜の街角で")


def test_the_players_own_name_counts_in_an_unspaced_script():
    """A2: `re.findall(r"[A-Za-z']+", player_name)` found no parts of a
    Japanese name, so third-person narration of the player scored zero on
    every beat and the voice fell to whatever the tie broke to."""
    assert common._narration_person_counts(
        "Sarah steps into the light.", "Sarah Moon")["third"] == 1
    assert common._narration_person_counts(
        "ヒナミは扉を開けた。", "ヒナミ")["third"] == 1
    assert common._narration_person_counts(
        "She steps into the light.", "Sarah Moon")["third"] == 0


def test_the_player_interiority_floor_fires_in_an_unspaced_script():
    """A2: `_mentions_player` is the gate on this whole floor, and it matched
    `\\b{form}\\b` -- so a name written straight against its particle was never
    seen, every sentence was skipped, and the floor that stops the Director
    deciding what the protagonist feels was inert for a Japanese story. The
    pack's own interior vocabulary was equally unreachable behind `\\b`."""
    assert common._mentions_player("sarah moon steps forward", "Sarah Moon")
    assert common._mentions_player("ヒナミは前に出た", "ヒナミ")
    assert not common._mentions_player("the stranger steps forward",
                                       "Sarah Moon")
    en = common._check_player_interiority_authority(
        "Sarah Moon opens the door. She takes in the genuine terror in "
        "those wide eyes.", "Sarah Moon")
    assert en and "terror" in en[0]
    with language_scope("ja"):
        ja = common._check_player_interiority_authority(
            "ヒナミは扉を開けた。ヒナミの目には本当の恐怖があった。", "ヒナミ")
        assert ja and "恐怖" in ja[0] and "本当" in ja[0]
        # The exemption reads the declaration the same way: what the player
        # wrote themselves is theirs to declare, in either script.
        assert common._check_player_interiority_authority(
            "ヒナミは扉を開けた。ヒナミの目には本当の恐怖があった。", "ヒナミ",
            declared_text="恐怖を感じる") == []
    assert common._check_player_interiority_authority(
        "Sarah Moon takes in the genuine terror in those wide eyes.",
        "Sarah Moon", declared_text="the terror is mine to name") == []


def test_a_named_subject_and_its_predicate_survive_the_particle():
    """A2: `_named_cast_subject`, `bind_sequence_targets` and
    `_strip_subject` all matched a cast name with `\\b`, so in an unspaced
    script an act named nobody, bound no target and left no predicate for any
    verb check to read."""
    assert common._named_cast_subject(
        "ヒナミは扉を開けた", {"ヒナミ": ["ヒナミ"]}) == "ヒナミ"
    assert common._named_cast_subject(
        "Reya opens the door", {"Reya": ["reya"]}) == "Reya"
    assert common._named_cast_subject(
        "Reyanne opens the door", {"Reya": ["reya"]}) is None, \
        "a Latin name still refuses to match inside a longer word"

    sequence = [{"type": "action", "attempt": "ヒナミに手を伸ばす",
                 "targets": []},
                {"type": "action", "attempt": "reaches for reya",
                 "targets": []}]
    assert common.bind_sequence_targets(
        sequence, {"ヒナミ": ["ヒナミ"], "Reya": ["reya"]}) == 2
    assert sequence[0]["targets"] == ["ヒナミ"]
    assert sequence[1]["targets"] == ["Reya"]

    assert common._strip_subject("ヒナミは扉を開けた", "ヒナミ") == "は扉を開けた"
    assert common._strip_subject(
        "Sarah Moon opens the door", "Sarah Moon") == " opens the door"
    assert common._strip_subject(
        "Sarah Moon's hand opens the door", "Sarah Moon") \
        == " hand opens the door"
    assert common._strip_subject("Mooney opens it", "Moon") == "", \
        "a Latin name still refuses to open a longer word"

    # `_predicate_heads` measured its window with `[A-Za-z']+`, so every
    # conjunct of an unspaced predicate had the empty string for a head.
    assert common._predicate_heads("takes a half-step closer", 3) == [
        ("takes a half", "takes a half-step closer")]
    heads = common._predicate_heads("は静かに扉を開けた", 3)
    assert heads and heads[0][0].strip()


def test_an_attempt_opening_with_a_name_is_seen_in_either_script():
    """A2, the same class one expression along: shape 1 of
    `authored_other_subject` demanded a space or an apostrophe after the name,
    which an unspaced script never writes."""
    with language_scope("ja"):
        assert common.authored_other_subject(
            {"type": "action", "verb": "思う", "attempt": "ヒナミは静かに思う"},
            {"7": ["ヒナミ"]}) == "7"
    assert common.authored_other_subject(
        {"type": "action", "verb": "remembers",
         "attempt": "reya remembers the door"}, {"7": ["reya"]}) == "7"
    assert common.authored_other_subject(
        {"type": "action", "verb": "remembers",
         "attempt": "reyanne remembers the door"}, {"7": ["reya"]}) is None
