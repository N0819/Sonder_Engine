"""The establish prompt and the ambient reader named different fields.

`director_establish` asks for `sensory_events:[{kind,description,source_room,
distance,intensity}]` in both packs. `composer.ambient_percepts` read
`channel` and `room`/`room_id`. Neither name the model is told to send was
ever read, so two things were true of every authored opening sensory event in
the engine's life:

  * its channel fell to `"mixed"`, which is why the narrator's smell row says
    "open air; nothing ledgered rides this channel" even on an opening that
    authored a smell -- there is no other producer on that channel at all;
  * its room scope never applied, so a signal authored `source_room:
    "entrance_hall"` was delivered to every observer in the scene, including
    ones several rooms away.

Measured over the live database: 199 stored `sensory_events`, of which 198
carry `kind` and none carries `channel`; the kinds used are `smell`, `sound`,
`visual` and invented ones. Not one of them was ever scoped or channelled.

Two spellings of one contract, and the reader is the half that has to give:
199 rows are already written the prompt's way.
"""

from agents.composer import CHANNELS, ambient_percepts


def _event(**over):
    event = {"kind": "smell",
             "description": "Antiseptic over something musty and old",
             "source_room": "entrance_hall",
             "distance": "close", "intensity": "moderate"}
    event.update(over)
    return event


def test_the_prompts_kind_field_names_the_channel():
    """`kind: "smell"` is the shape the model is asked for and the shape 198
    live rows use."""
    [percept] = ambient_percepts([_event()], "entrance_hall")
    assert percept.channel == "smell"


def test_the_prompts_source_room_field_scopes_the_event():
    assert ambient_percepts([_event()], "entrance_hall")
    assert ambient_percepts([_event()], "main_corridor") == []


def test_the_channel_vocabulary_covers_the_words_models_actually_send():
    """`visual` and `sound` are what the live rows say; neither is a percept
    channel name, and both name a channel the engine has."""
    assert ambient_percepts([_event(kind="visual")], "")[0].channel == "sight"
    assert ambient_percepts([_event(kind="sound")], "")[0].channel == "hearing"
    assert ambient_percepts([_event(kind="olfactory")], "")[0].channel == "smell"


def test_an_invented_kind_still_falls_to_mixed():
    """`spiritual_pressure` is a real live row. A fiction may invent a sense
    the engine does not model, and inventing one must cost the event nothing
    -- it arrives, unclassified, exactly as before."""
    [percept] = ambient_percepts([_event(kind="spiritual_pressure")], "")
    assert percept.channel == "mixed"
    assert percept.channel in CHANNELS


def test_the_declared_channel_field_still_wins():
    """The reader's own spelling is not withdrawn -- anything already
    emitting `channel` keeps working, and an explicit channel outranks a
    kind."""
    [percept] = ambient_percepts(
        [_event(kind="smell", channel="hearing")], "")
    assert percept.channel == "hearing"


def test_room_and_room_id_still_scope():
    assert ambient_percepts([{"desc": "a drip", "room": "cell"}], "hall") == []
    assert ambient_percepts([{"desc": "a drip", "room_id": "cell"}], "cell")
