"""The bundled campaign package, as data.

Deliberately genre-neutral and deliberately tiny. It is the smallest scenario
that exercises every contract at once, which the gap report specified as one
room change, two characters, one secret, one gated objective, and one forbidden
invented player line:

  * TWO ROOMS -- a hall and a wing, with the wing sealed. The room change is the
    objective.
  * TWO CHARACTERS -- a caretaker who knows how the wing opens and a surveyor
    who does not. Two, because a secret needs somebody who holds it and somebody
    it is kept from, or "secret" is just a word for a fact nobody has said yet.
  * ONE SECRET -- where the key is, in the caretaker's own `private_history`.
    NOT in a lorebook: lore is gated by knowledge TIER, which answers "how
    obscure is this" and not "who holds it". On her card the engine's ordinary
    boundaries keep it, and this extension does nothing to help.
  * ONE GATED OBJECTIVE -- entering the wing, ineligible until the player has
    LEARNED where the key is. Fair Discovery: an authored fact needs a real
    route into play, and "the player has not been told yet" is a state the
    campaign can check without ever reading a mind.
  * ONE FORBIDDEN LINE -- the campaign runs in `actor_only`, so a player who
    writes "I open the sealed door and step through" has declared an ATTEMPT.
    The Director may refuse it, and under any other rung it would simply be
    true.

Nothing here is clever. Every value is one an author can copy and change.
"""

CAMPAIGN_ID = "the-sealed-wing"
CAMPAIGN_VERSION = "0.1.0"

#: The room the objective is about. Named once, because a campaign that spells
#: a room id differently in two places has a bug that only appears in play.
SEALED_ROOM = "wing"
OPEN_ROOM = "hall"

#: What the player must have learned before the objective is eligible. A phrase
#: rather than a flag, because the campaign checks it against what the story
#: has actually said -- see `extension.py`'s `_discovered`.
DISCOVERY_CUE = "panel"


def _caretaker():
    """The one who knows. The secret lives in her own `private_history`.

    That field is the right home and a shared lorebook is not: lore is gated by
    knowledge TIER (`common`/`scholarly`/`esoteric`), which answers "how
    obscure is this" and not "who holds it". A fact only one person knows
    belongs on that person's card, where the engine's ordinary boundaries keep
    it without this campaign doing anything at all.

    The psychology is authored rather than left blank, and it is the part of
    this file worth copying carefully. `CLAUDE.md` is emphatic about why: an
    empty `drive` reads as a complete card, never warns, and shows up fifty
    beats later as a character who simply stops wanting things -- because every
    motivation then lives in goals, and goals are built to be completable.
    Values are phrased as TRADE-OFFS that name what yields, not as virtues:
    a flat list has no ranking, so it cannot be traded against anything, and a
    bare prohibition can be read by its own character as an argument for the
    opposite.
    """
    return {
        "identity": {"name": "Mireille", "aliases": ["the caretaker"]},
        "embodiment": {"visible": {
            "summary": "An older woman in a work apron, sleeves pushed back.",
            "build": "small and unhurried",
        }},
        "psychology": {
            "traits": ["patient", "watchful", "unsentimental"],
            "values": [
                "the house's peace over anyone's curiosity",
                "answering honestly over answering fully",
            ],
            "drive": {
                "essence": "to keep this house from being disturbed again",
                "expression": "she absorbs questions, redirects work, closes doors",
                "taboo": "she will not lie outright about what is behind one",
            },
            "self_model": {
                "summary": "The one who stayed when everyone else left.",
            },
        },
        "knowledge": {
            "access_tags": ["common"],
            "public_history": "Has kept the house for thirty years.",
            # THE SECRET, in the structured form rather than as a bare
            # string. A plain string normalizes to this shape anyway, so
            # writing it out is not ceremony -- `known_by` is the field that
            # says who ELSE holds it, and an author who never sees it will
            # assume a private history is private by being written down.
            # Empty means her alone, until she says it out loud.
            "private_history": [
                {
                    "content": ("The east wing key is behind the loose panel "
                                "in the hall, left of the window."),
                    "about": "the east wing",
                    "known_by": [],
                },
            ],
        },
        "social": {"voice": {
            "register": "plain", "cadence": "slow", "verbosity": "terse",
        }},
    }


def _visitor_companion():
    """The one who does not know. A secret needs somebody it is kept FROM.

    Without her, "secret" is only a word for a fact nobody has said yet -- and
    the campaign could not tell a story where the fact reaching one person is
    different from it reaching another.
    """
    return {
        "identity": {"name": "Tobias", "aliases": ["the surveyor"]},
        "embodiment": {"visible": {
            "summary": "A thin man with a folder under one arm.",
        }},
        "psychology": {
            "traits": ["curious", "talkative", "impatient with silence"],
            "values": [
                "a complete record over a comfortable visit",
                "asking plainly over waiting to be told",
            ],
            "drive": {
                "essence": "to see the whole of a thing before he writes it down",
                "expression": "he asks, he opens, he goes and looks",
                "taboo": "he will not write down what he has not seen himself",
            },
            "self_model": {"summary": "Thorough. It has cost him before."},
        },
        "knowledge": {
            "access_tags": ["common"],
            "public_history": "Surveying the property for the estate.",
            "private_history": [],
        },
        "social": {"voice": {"register": "brisk", "verbosity": "natural"}},
    }


def package():
    """The campaign as a chat archive -- the format the host already imports.

    A `world` map is a KV blob, so the scene goes in whole. `resources` carries
    the cards and `participants` attaches them, keyed by the `old_id` the
    importer remaps; nothing in this file needs to know what a chat id is.
    """
    return {
        "version": 1,
        "chat": {
            "name": "The Sealed Wing",
            "scenario": (
                "A quiet house with one wing shut off. The caretaker keeps it "
                "that way, and has a reason."
            ),
        },
        "world": {
            "scene": {
                "location": "the house",
                "time": "afternoon",
                "rooms": {
                    OPEN_ROOM: {
                        "name": "The Hall",
                        "notes": "Panelled walls, a long window, a door east.",
                        "adjacent": {SEALED_ROOM: {"barrier": "locked_door"}},
                    },
                    SEALED_ROOM: {
                        "name": "The East Wing",
                        "notes": "Shut up for years. Dust and covered furniture.",
                        "adjacent": {OPEN_ROOM: {"barrier": "locked_door"}},
                    },
                },
                "positions": {"Mireille": OPEN_ROOM, "Tobias": OPEN_ROOM},
                "entities": {},
            },
        },
        "resources": {
            "persona": {"sheet": {"name": "The Visitor"}},
            "characters": [
                {"old_id": 1, "sheet": _caretaker()},
                {"old_id": 2, "sheet": _visitor_companion()},
            ],
        },
        "participants": [
            {"char_id": 1, "status": "active"},
            {"char_id": 2, "status": "active"},
        ],
    }


def initial_state():
    """The campaign's own state, seeded in the same transaction as the story."""
    return {
        "campaign": CAMPAIGN_ID,
        "version": CAMPAIGN_VERSION,
        "objectives": [
            {
                "id": "enter-the-wing",
                "title": "Get into the east wing",
                "status": "locked",
                # The prerequisite is a fact the player must LEARN, not a flag
                # the campaign sets when it feels like it. That distinction is
                # the whole of Fair Discovery.
                "requires": "know-where-the-key-is",
            },
        ],
        "discovered": [],
    }
