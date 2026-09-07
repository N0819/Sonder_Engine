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
