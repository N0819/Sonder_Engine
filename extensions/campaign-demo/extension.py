"""The reference campaign layer: the whole vertical slice.

`cohesion-demo` shows a pipeline stage. `overlay-demo` shows the reader-facing
half. This one shows what a CAMPAIGN needs, which is a different list: it starts
the story rather than joining one, holds rules that outlive any beat, sees the
world between beats to decide anything, shows a person only what that person
has, and relies on the player not being able to write the world.

Five host contracts, one each:

    api.provision_story   -- the story, its cast, its map and this campaign's
                             own state, created atomically or not at all
    api.director_context   -- the campaign's standing rules, in front of the
                             DECISION rather than appended to the verdict
    api.add_commit_domain  -- mission state advanced inside the turn's own
                             transaction, so a rolled-back beat cannot leave a
                             completed objective behind
    api.player_view        -- what the panel is allowed to render
    player_authority       -- `actor_only`, declared at provisioning

The campaign itself is in `campaign.py` and is deliberately tiny. Everything
interesting here is the plumbing, and every call is one an author can copy.
"""

from .campaign import (CAMPAIGN_ID, CAMPAIGN_VERSION, DISCOVERY_CUE, OPEN_ROOM,
                      SEALED_ROOM, initial_state, package)

#: The two Director rules, one per phase, and they say different things because
#: the phases ask different questions. Interpret reads what the player DECLARED;
#: resolve decides what it ACHIEVED. A single rule serving both would either
#: bias the reading of the player's own words or fail to bind the outcome.
SEALED_INTERPRET = (
    "The east wing is sealed and its door is locked. A declaration that enters "
    "it is a declaration of an ATTEMPT, however confidently it is worded."
)
SEALED_RESOLVE = (
    "The east wing is sealed. No attempt opens that door without the key, and "
    "the key is not on any body in the house. An attempt may be described, felt "
    "and refused; it does not succeed."
)
OPENED_RESOLVE = (
    "The east wing's key has been found. The door opens to whoever holds it, "
    "and the wing is an ordinary room from here on."
)


def register(api):
    api.add_commit_domain("mission", lambda view: _advance(api, view))
    api.add_route("/campaign", lambda request: _campaign(api, request))
    api.add_route("/start", lambda request: _start(api, request),
                  methods=("POST",))


# ------------------------------------------------------------- provisioning


def _start(api, request):
    """Provision the bundled campaign. The player pressed Start."""
    result = api.provision_story(
        package(),
        state=initial_state(),
        package_id=CAMPAIGN_ID,
        package_version=CAMPAIGN_VERSION,
        # Declared here rather than set afterwards: a campaign whose premise is
        # that the player may not write the world cannot ask for that after the
        # first beat has already been played under the other rule.
        player_authority="actor_only",
    )
    _install_rules(api, result["chat_id"], unlocked=False)
    return result


def _install_rules(api, chat_id, *, unlocked):
    """Put the campaign's standing rules in front of the Director.

    Rewritten rather than appended to, which the host enforces anyway: a rule
    that is no longer true has to STOP being said, and an injector that only
    ever adds is one that tells the Director the wing is sealed for the rest of
    the story.
    """
    api.director_context(chat_id).set(
        interpret=SEALED_INTERPRET if not unlocked else "",
        resolve=SEALED_RESOLVE if not unlocked else OPENED_RESOLVE,
    )


# ------------------------------------------------------------ mission state


def _advance(api, view):
    """One commit domain, run inside the turn's transaction.

    Deterministic by construction: it reads what the story SAID this beat and
    compares it against the objective's stated prerequisite. It never asks a
    model, never reads a mind, and cannot invent a discovery -- if the fact did
    not reach the player's own view, nothing here advances.

    Inside the transaction rather than in `on_turn_committed` because a beat
    that rolls back must not leave a completed objective behind. An objective
    the player can see and the story never earned is worse than one that
    unlocks a beat late.
    """
    state = view.state.get() or {}
    if state.get("campaign") != CAMPAIGN_ID:
        return                                   # not our story
    if _objective(state, "enter-the-wing").get("status") != "locked":
        return                                   # already open; nothing to do

    if not _discovered(view):
        return

    objective = _objective(state, "enter-the-wing")
    objective["status"] = "available"
    discovered = list(state.get("discovered") or [])
    if objective["requires"] not in discovered:
        discovered.append(objective["requires"])
    state["discovered"] = discovered
    view.state.set(state)
    _install_rules(api, view.chat_id, unlocked=True)


def _discovered(view):
    """Did the secret reach the PLAYER this beat, through a real route?

    The player's own delivered view is the evidence, and it is the correct
    evidence: perception already decided what reached them, so this asks a
    question the engine has answered rather than answering it again. A
    caretaker who merely KNOWS where the key is changes nothing here; a
    caretaker who says so within earshot does.

    Substring matching on one authored cue is crude, and crude is the point in a
    reference: an author swapping this for their own recogniser should be able
    to see exactly what it replaced.
    """
    outcome = view.step_content("perception_outcome") or {}
    views = outcome.get("views")
    if not isinstance(views, dict):
        return False
    return DISCOVERY_CUE in str(views.get("player") or "").casefold()


def _objective(state, objective_id):
    for objective in state.get("objectives") or []:
        if isinstance(objective, dict) and objective.get("id") == objective_id:
            return objective
    return {}


# -------------------------------------------------------------------- routes


def _campaign(api, request):
    """What the panel renders: mission state, plus a PLAYER-SAFE story view.

    `api.story_view` would answer more and is the right read for the campaign's
    own rules. It is the wrong read for a panel a player is looking at, and the
    difference is the entire reason both exist -- a panel fed canonical truth
    would show the player which room the key is in before anyone told them.
    """
    chat_id = request.chat_id
    if chat_id is None:
        return {"chat_id": None, "campaign": None}

    state = api.state(chat_id).get() or {}
    if state.get("campaign") != CAMPAIGN_ID:
        return {"chat_id": chat_id, "campaign": None}

    seen = api.player_view(chat_id, "player")
    return {
        "chat_id": chat_id,
        "campaign": state.get("campaign"),
        "version": state.get("version"),
        "objectives": state.get("objectives") or [],
        "authority": api.story_view(chat_id)["player_authority"]["mode"],
        # Straight from the projection. Absent keys stay absent -- the panel
        # renders what is there and says nothing about what is not, because a
        # placeholder is a claim the engine did not make.
        "where": (seen.get("location") or {}).get("name"),
        "turn": (seen.get("turn") or {}).get("idx"),
        "view": (seen.get("perception") or {}).get("view"),
        "knows": seen.get("knows") or [],
        "sealed": SEALED_ROOM,
        "open": OPEN_ROOM,
    }
