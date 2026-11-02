"""Who told a body something is held by KEY, and named only where it speaks.

`heard_from` was a body key from ordinary talk, a DISPLAY NAME from formal
reports, cross-charter gossip and delivered errands, and free text from
authored plants -- and its readers assume the key: `check_reports` mints a
`report_refuted` about the teller and `update_judgments_from_minds` weighs the
teller by the holder's regard, both keyed by body key. Measured (audit
world_charter_behaviours F9, world_charter_core F12): a superior who checked
a subordinate's report formed a stance on "Ann Tull", a subject that is no
body and that no reader looks up, and the regard it holds for its subordinate
was ignored. One vocabulary now: the teller's body key within its own
institution, a qualified person id (`charter/body`) across institutions, the
author's own words for a teller the registry does not hold; names are
rendered at the voice."""
from world.charter import (check_reports, normalize_charter,
                           report_to_superiors, update_judgments_from_minds)
from world.charter_runtime import (cross_charter_gossip, normalize_registry,
                                   person_id)


def _watch():
    state = normalize_charter({
        "key": "watch",
        "upkeeps": {"road": {"place": "gate", "level": 0.9, "floor": 0.2,
                             "drift_per_hour": 0.0,
                             "service_per_hour": 1.0}},
        "posts": {
            "gate_watch": {"place": "gate", "serves": [],
                           "reports_to": "watch_captain"},
            "watch_captain": {"place": "gate", "serves": []}},
        "bodies": {"clerk:0001": {"name": "Ann Tull", "place": "gate"},
                   "reeve:0001": {"name": "Ysra Vale", "place": "gate"}},
        "watch": {"gate_watch": "clerk:0001",
                  "watch_captain": "reeve:0001"}})
    state["minds"] = {"clerk:0001": {"news:upkeep_out_of_band:road@1.0000": {
        "kind": "news", "body": "news:upkeep_out_of_band:road@1.0000",
        "event_kind": "upkeep_out_of_band", "about": "road",
        "place": "gate", "happened_at": 1.0, "strength": 1.0,
        "as_of_hours": 1.0, "heard_from": None,
        "provenance": "witnessed_surface"}}}
    return state


def test_a_formal_report_is_held_from_the_subordinates_key():
    state = _watch()
    minds, told = report_to_superiors(
        state["minds"], state["watch"], state["posts"], state["bodies"],
        naming=state["naming"], at_hours=2.0)
    assert told == 1
    claim = minds["reeve:0001"]["news:upkeep_out_of_band:road@1.0000"]
    assert claim["heard_from"] == "clerk:0001"


def test_a_refuted_report_files_its_stance_under_the_tellers_key():
    state = _watch()
    minds, _told = report_to_superiors(
        state["minds"], state["watch"], state["posts"], state["bodies"],
        naming=state["naming"], at_hours=2.0)
    # The road is in band: the report of it failing is refuted on sight.
    minds, checks = check_reports(minds, state["bodies"], state["upkeeps"],
                                  3.0)
    assert checks >= 1
    judgments, _moves = update_judgments_from_minds(
        {}, minds, politics=state.get("politics"),
        norms=state.get("social_norms"))
    assert "clerk:0001" in (judgments.get("reeve:0001") or {})
    assert "Ann Tull" not in (judgments.get("reeve:0001") or {})


def test_gossip_across_institutions_is_held_from_a_qualified_teller():
    home = _watch()
    home["minds"]["clerk:0001"]["news:upkeep_out_of_band:road@1.0000"][
        "claim_text"] = "the east road is washed out"
    visitors = normalize_charter({
        "key": "visitors", "upkeeps": {}, "posts": {},
        "bodies": {"clerk:0001": {"name": "Vela South", "place": "gate"}}})
    registry = normalize_registry({"items": {
        "watch": {"state": home}, "visitors": {"state": visitors}}})
    cross_charter_gossip(registry)
    held = [claim for claims in
            (registry["items"]["visitors"]["state"].get("minds") or {})
            .values() for claim in claims.values()
            if claim.get("heard_from")]
    assert held, "the visitor took the news on"
    assert {claim["heard_from"] for claim in held} <= {
        person_id("watch", "clerk:0001"), person_id("watch", "reeve:0001")}


def test_the_voice_names_a_teller_as_the_listener_could():
    """A teller from another house is a stranger to the listener: its post
    words, never its key and never a name it did not learn."""
    from world.charter_runtime import _member_namer, identity_index
    home = _watch()
    visitors = normalize_charter({
        "key": "visitors", "upkeeps": {}, "posts": {},
        "bodies": {"vela": {"name": "Vela South", "place": "gate"}}})
    registry = normalize_registry({"items": {
        "watch": {"state": home}, "visitors": {"state": visitors}}})
    state = registry["items"]["visitors"]["state"]
    person = _member_namer(state, "vela", "visitors",
                           identity_index(registry).display("visitors"),
                           registry=registry)
    said = person(person_id("watch", "clerk:0001"))
    assert said
    assert "Ann Tull" not in said and ":" not in said and "/" not in said
