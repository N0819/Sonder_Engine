"""Reference extension: a stage, a per-story score, and nothing else.

This file exists to show the whole shape of a Tier-2 extension in one screen.
It touches NO engine file: the stage's key, its position in the plan, its
persistence and its panel all come from the manifest plus the `api` handed to
`register` below. Adding it does not require an entry in `runtime.STEP_HANDLERS`,
a row in `schemas.SCHEMA_MAP`, a field on `PipelineContext`, or a line in
`commit.py` -- which is the point of the extension system, and the whole of
`agents/README.md`'s add-a-stage checklist that a third party must not have to
follow.

Deliberately deterministic: it makes no model call, so it costs the turn
nothing, runs identically under stubbed-provider tests, and its output is a pure
function of the beat the Director just resolved.
"""

# Channels a specialist writes when a body takes damage or a state lands on
# someone. Named as CHANNELS rather than as any particular injury: the engine's
# vocabulary is what stays true across every story.
HARM_CHANNELS = ("conditions", "vitals")

DEFAULT_STATE = {"cohesion": 50}
DELTA_LIMIT = 3
#: How many readings the story keeps. Bounded because this rides `world` KV,
#: which is copied wholesale into every checkpoint, branch and archive -- an
#: unbounded log here would grow every one of them forever.
HISTORY_LIMIT = 40


def pulse(view, api, nonce):
    """Read the resolved beat; return a bounded cohesion delta and its grounds.

    `view` is a read-only slice of the running turn -- finished step output
    only. An extension stage never receives the PipelineContext, so it cannot
    move a fact between two minds even by accident.
    """
    evidence = []
    delta = 0

    if view.dialogue_log:
        delta += 1
        evidence.append(f"{len(view.dialogue_log)} line(s) of dialogue exchanged")

    diff = view.state_diff
    for channel in HARM_CHANNELS:
        entries = diff.get(channel)
        count = len(entries) if isinstance(entries, (list, dict)) else 0
        if count:
            delta -= count
            evidence.append(f"{count} {channel} change(s) in the resolved diff")

    delta = max(-DELTA_LIMIT, min(DELTA_LIMIT, delta))
    return {"cohesion_delta": delta,
            "evidence": evidence,
            "turn_idx": view.turn_idx}


def register(api):
    """Called ONCE when the host enables this extension."""

    stage_key = api.add_stage(
        "pulse",
        anchor="after:director_resolve",
        label="Cohesion · pulse",
        handler=pulse,
        # A flaky extension degrades to a visible warning and an {"error": ...}
        # step, never a dead turn.
        on_error="warn",
    )

    @api.on_turn_committed
    def apply_pulse(turn):
        """Fold this turn's delta into the story's score, once it is durable.

        The only place `state.set()` is permitted: a write made mid-pipeline
        would land outside the turn's transaction and survive a rollback that
        undid everything it was computed from.
        """
        content = turn.step_content(stage_key)
        if not isinstance(content, dict):
            return
        delta = content.get("cohesion_delta")
        if not isinstance(delta, (int, float)):
            return
        state = dict(turn.state.get(DEFAULT_STATE) or DEFAULT_STATE)
        score = float(state.get("cohesion", DEFAULT_STATE["cohesion"]))
        state["cohesion"] = max(0.0, min(100.0, score + float(delta)))
        state["last_turn"] = turn.turn_idx
        history = state.get("history")
        history = list(history) if isinstance(history, list) else []
        history.append({"turn": turn.turn_idx, "delta": delta,
                        "cohesion": state["cohesion"]})
        state["history"] = history[-HISTORY_LIMIT:]
        turn.state.set(state)

    @api.on_step("character:*")
    def watch_minds(step_key, content):
        """Read-only: proof that a step observer sees decisions land.

        This one only counts, because counting is enough to show the seam.
        Note what it does NOT do -- it has the content of one mind's decision
        and does not put any of it anywhere another mind can reach.
        """
        api.log.debug("cohesion saw %s", step_key)

    def history(request):
        """`GET /api/extensions/cohesion-demo/x/history?chat_id=N`.

        An extension's own route: the panel reads its history from here rather
        than from a host endpoint that would have to learn what cohesion is.
        """
        chat_id = request.chat_id
        if chat_id is None:
            raise ValueError("chat_id is required")
        state = api.state(chat_id).get(DEFAULT_STATE) or DEFAULT_STATE
        return {"chat_id": chat_id,
                "cohesion": state.get("cohesion"),
                "history": state.get("history") or []}

    api.add_route("/history", history)
