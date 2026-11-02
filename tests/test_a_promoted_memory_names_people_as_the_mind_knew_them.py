"""A promoted mind remembers people, posts and places in words, as it knew
them -- never by the engine's keys.

`charter_promote.remembered` rendered raw keys into memory CONTENT: "heard
from gate_watch:0002 that custom failing at taproom", "gate_watch:0002 said
the fault was gate_watch:0001's", "knows gate_watch:0002", "has stood
gate_watch through 12 watches" -- stored verbatim as the character's own
memories, while the same promotion mapped the keys to names for its
relationship graph, so the character trusted "Odo Brack" and remembered
"gate_watch:0002" (audit world_charter_behaviours F10). A person this body
knows is named, one it does not is its post, a figure is the label its own
claim saw, a post is its title and a room its name."""
from world.charter import normalize_charter
from world.charter_promote import remembered


def _gate():
    charter = normalize_charter({
        "key": "gatehouse",
        "scene": {"rooms": {
            "taproom": {"name": "The Taproom", "adjacent": []},
            "arch": {"name": "The Arch", "adjacent": []}}},
        "upkeeps": {"custom": {"place": "taproom", "level": 0.9,
                               "floor": 0.2, "drift_per_hour": 0.0,
                               "service_per_hour": 1.0}},
        "posts": {"gate_watch": {"place": "arch", "serves": ["custom"]},
                  "cook": {"place": "taproom", "serves": ["custom"]}},
        "bodies": {
            "gate_watch:0001": {"name": "Ilse Varn", "place": "arch",
                                "home_post": "gate_watch"},
            "gate_watch:0002": {"name": "Odo Brack", "place": "arch",
                                "home_post": "gate_watch"},
            "cook:0001": {"name": "Tam Reddy", "place": "taproom",
                          "home_post": "cook"},
        },
        "naming": {"titles": {"posts": {"gate_watch": "Gate Warden",
                                        "cook": "Cook"}}},
    })
    me = "gate_watch:0001"
    charter["stood"] = {me: {"gate_watch": 12}}
    charter["heard_blame"] = {me: ["gate_watch:0002"]}
    charter["minds"] = {me: {
        # She knows Odo (a claim keyed by him); she has never met the cook.
        "gate_watch:0002": {"body": "gate_watch:0002", "competence": {},
                            "believed_available": True, "strength": 0.9,
                            "as_of_hours": 0.0, "heard_from": None},
        "news:upkeep_out_of_band:custom@4.0000": {
            "kind": "news", "body": "news:upkeep_out_of_band:custom@4.0000",
            "event_kind": "upkeep_out_of_band", "about": "custom",
            "place": "taproom", "happened_at": 4.0, "strength": 0.8,
            "as_of_hours": 4.0, "heard_from": "gate_watch:0002"},
        "news:body_unable:cook:0001@6.0000": {
            "kind": "news", "body": "news:body_unable:cook:0001@6.0000",
            "event_kind": "body_unable", "about": "cook:0001",
            "place": "taproom", "happened_at": 6.0, "strength": 0.7,
            "as_of_hours": 6.0, "heard_from": "gate_watch:0002"},
        "Sarah Moon": {"kind": "figure", "body": "Sarah Moon",
                       "surface": {"label": "the slight woman"},
                       "place": "arch", "strength": 1.0, "as_of_hours": 2.0,
                       "heard_from": None},
    }}
    charter["commitments"] = {"c1": {
        "id": "c1", "kind": "promise", "promisor": "Sarah Moon",
        "beneficiary": me, "terms": "to bring word", "state": "open",
        "opened_at_hours": 2.0, "recognized_by": [me]}}
    return charter, me


# Every engine spelling a memory used to carry, and the two names she never
# learned (Sarah Moon is a figure she saw as "the slight woman"; Tam Reddy a
# cook she has no claim about). An upkeep has no name of its own in this
# engine and reads as its id in words, as the voice already says it.
_KEYS = ("gate_watch:0001", "gate_watch:0002", "cook:0001", "gate_watch",
         "taproom", "Sarah Moon", "Tam Reddy")


def test_no_memory_content_carries_an_engine_key_or_an_unlearned_name():
    charter, me = _gate()
    for memory in remembered(charter, me):
        content = memory["content"]
        for key in _KEYS:
            assert key not in content, (key, content)


def test_the_people_she_knows_are_named_and_the_rest_are_their_posts():
    charter, me = _gate()
    text = " | ".join(m["content"] for m in remembered(charter, me))
    assert "Odo Brack" in text
    assert "the slight woman" in text
    assert "The Taproom" in text
