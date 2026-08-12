#!/usr/bin/env python3
"""A story played by a real model, to find out whether the prompts land.

Every other drive here authors the model's side. That measures whether the
engine CARRIES a mechanism. This measures whether a model, shown the engine's
actual system prompt and payload, REACHES for one -- which is a claim about
the prompts, and the one thing no amount of hand-authoring can establish.

Only the opening scene is authored, because establishing a world is what a
user does before play starts. From the first beat onward every stage is the
model's: interpret, resolve, perception for each perceiver, each character,
the narrator, mapping, and every off-screen rung. Nothing is scripted, and
nothing is retried by hand. `llm_quality` validates and repairs exactly as it
would for a paying user, so a rejected op is a real rejection.

The player's inputs are written to create OCCASIONS, never to dictate
encodings. "I pay the rider two coins to carry word east" is a thing a player
would type; whether that becomes a `courier_ops` entry or evaporates into
prose is precisely what is being measured. If a mechanism never fires here,
the honest reading is that the prompt does not ask for it clearly enough --
not that the player failed to say the magic word.

    NANOGPT_API_KEY=... OPENROUTER_API_KEY=... ENGINE_DB=scratch.db \\
        python3 tools/model_playthrough.py --out DIR --capture CAP

Costs real money. Keys are read from the environment and never written into
the repository or into any artefact this harness produces.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.offscreen_drive import _require_scratch  # noqa: E402
from tools.quest_drive import QuestAuthor, build_story  # noqa: E402

#: Player inputs only. Each one is an ordinary thing to type, and each is an
#: occasion for a mechanism the fire-rate table has never seen a model reach
#: for. The comment on each says what it is an occasion FOR -- it is not a
#: hint to the model, which never sees this file.
BEATS = [
    # A populous place: an occasion for a crowd rather than named extras.
    "I come up into the market square. It is packed and nobody is buying.",
    "I listen to what the people around me are actually saying.",
    # An occasion for a telling: I know something, Sera does not.
    "I tell Sera what I saw at the well this morning.",
    # An occasion for an artifact: something legible, left standing.
    "I write out what happened to the well on a board and nail it up where "
    "the crowd can read it.",
    "I watch to see whether anyone stops to read it.",
    # An occasion for a courier: a body, a route, a message, a payment.
    "I find a rider heading east and pay him two coins to carry word to "
    "Siege Town that the wells here have been sealed.",
    "I watch him take the road out of the square.",
    # An occasion for a caravan: a body with STOPS that trades news at each.
    "I ask the salt caravan master when he next goes east, and whether he "
    "will carry the same word at each stop along the way.",
    "I help load his carts while we talk.",
    # An occasion for a plan or project: a stated intention with stages.
    "I tell Bryn I mean to reach the Ashen Keep before the week is out, and "
    "ask him to hold the village until I am back.",
    # Time, so the off-screen world has something to do.
    "I sleep until first light.",
    "I go down to the well to see whether anything has changed overnight.",
    # An occasion for a report to come back the other way.
    "I ask whether anyone has come back from the east with news.",
    "I take the road east.",
]


def authored_establish(author):
    """The opening scene, and only the opening scene.

    Authoring the world a story starts in is what a user does; authoring what
    happens in it is what this harness exists NOT to do. Establish is scripted
    so that the six rooms, their adjacency and the cast are the same world the
    other drives use -- otherwise a run that fired nothing would be ambiguous
    between a prompt that does not land and a world with no road on it.
    """
    return author.default("director_establish")


#: Every stage on one model, so a mechanism that never fires cannot be blamed
#: on a weak model for that role. Perception is the exception: it is 46% of
#: all stage calls (234 of 505 in a captured 51-beat story) because it runs
#: once per perceiver, so it gets the fast non-thinking model. Neither
#: `:thinking` variant is used -- reasoning is billed as output tokens, and
#: measured wall-clock on this pipeline tracks output tokens almost exactly.
#: SOURCED, NOT COPIED. This was a hardcoded tuple, and by the time anyone
#: looked it had drifted past `character_major` and every Director specialist
#: -- so a harness whose whole job is "seed every role on one model" was
#: quietly seeding a subset, and any role it missed fell through to whatever
#: `default` happened to be. Reading the real list means it cannot drift again.
from providers import ROLES as _PROVIDER_ROLES

ROLES = tuple(_PROVIDER_ROLES)
MAIN_MODEL = "minimax/minimax-m3"
PERCEPTION_MODEL = "mistral-code-agent-latest"
EMBEDDING_MODEL = "perplexity/pplx-embed-v1-4b"

#: `--fast`. Free and very quick, and everything sent to it is used to TRAIN.
#:
#: That is fine for exactly what this harness does and for nothing else. The
#: only things it transmits are the engine's own system prompts -- already
#: public, this repository is open -- and a wholly invented story about a
#: smith's apprentice in a valley that does not exist. No user story, no
#: private chat, no credential, no personal data.
#:
#: Never point this preset at a real story.
#:
#: It takes perception too, rather than leaving that role on a code model.
#: Measured: `mistral-code-agent-latest` was slower here than its headline
#: throughput suggests, and since wall-clock on this pipeline is generation-
#: bound, the fastest generator wins the role that runs once per perceiver.
FAST_MAIN_MODEL = "meta/muse-spark-1.2-contributor"
FAST_PERCEPTION_MODEL = "meta/muse-spark-1.2-contributor"


def seed_providers(db, main_model=MAIN_MODEL,
                   perception_model=PERCEPTION_MODEL):
    """Register the two providers this run needs, from the environment.

    Credentials are read from `NANOGPT_API_KEY` and `OPENROUTER_API_KEY` and
    never live in this file, in the repository, or in any artefact this
    harness writes. The scratch database they land in is outside the tree and
    is deleted with the job.

    Embeddings stay on OpenRouter deliberately. Repointing them would rebuild
    the vector space that recall was tuned against, and this run is about
    whether the prompts land -- not about retrieval.
    """
    import json as _json

    nano_key = os.environ.get("NANOGPT_API_KEY", "")
    if not nano_key:
        raise SystemExit(
            "Set NANOGPT_API_KEY (and OPENROUTER_API_KEY for embeddings).")

    nano = db.qi(
        "INSERT INTO providers(name,kind,base_url,api_key,enabled) "
        "VALUES(?,?,?,?,1)",
        ("nanogpt", "nanogpt", "https://nano-gpt.com/api/v1", nano_key))
    models = {role: {"provider": nano, "model": main_model} for role in ROLES}
    models["perception"] = {"provider": nano, "model": perception_model}

    # A third provider, seeded only when its key is present, so a run can put
    # the heavy roles somewhere with different decode economics. The measured
    # reason: on a reasoning model this engine's wall clock is output tokens
    # divided by decode rate -- resolve emitted 19,899 tokens in 347s -- so
    # WHERE a role runs matters more than how big its prompt is.
    fw_key = os.environ.get("FIREWORKS_API_KEY", "")
    if fw_key:
        db.qi("INSERT INTO providers(name,kind,base_url,api_key,enabled) "
              "VALUES(?,?,?,?,1)",
              ("fireworks", "generic",
               "https://api.fireworks.ai/inference/v1/", fw_key))

    cb_key = os.environ.get("CEREBRAS_API_KEY", "")
    if cb_key:
        db.qi("INSERT INTO providers(name,kind,base_url,api_key,enabled) "
              "VALUES(?,?,?,?,1)",
              ("cerebras", "generic", "https://api.cerebras.ai/v1", cb_key))

    router_key = os.environ.get("OPENROUTER_API_KEY", "")
    if router_key:
        router = db.qi(
            "INSERT INTO providers(name,kind,base_url,api_key,enabled) "
            "VALUES(?,?,?,?,1)",
            ("openrouter", "openrouter", "https://openrouter.ai/api/v1",
             router_key))
        models["embeddings"] = {"provider": router, "model": EMBEDDING_MODEL}

    db.set_setting("agent_models", _json.dumps(models))
    return models


def install(author):
    """The opening scene is authored; every other stage is a real model call.

    Only `director_establish` is intercepted. Everything below this -- the
    provider call, JSON parsing, strict validation, the repair pass and the
    fallback candidates -- runs exactly as it does for a paying user, so a
    rejected `courier_ops` entry here is a real rejection rather than a
    harness artifact.
    """
    import llm_quality

    real = llm_quality.complete_validated_json

    def routed(*, role, step_key, system, payload, **kw):
        if step_key.split(":")[0] == "director_establish":
            return authored_establish(author)
        if getattr(author, "capture_dir", ""):
            author._capture(step_key, system, payload)
        return real(role=role, step_key=step_key, system=system,
                    payload=payload, **kw)

    llm_quality.complete_validated_json = routed
    for mod in list(sys.modules.values()):
        if getattr(mod, "complete_validated_json", None) is not None \
                and mod is not llm_quality:
            mod.complete_validated_json = routed
    return routed


def play(db, cid, inputs):
    from agents.runtime import run_pipeline

    played = []
    for idx, player_input in enumerate(inputs):
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, player_input, time.time(), None))
        error = ""
        started = time.time()
        try:
            for _ in run_pipeline(cid, tid):
                pass
        except Exception as exc:              # noqa: BLE001 - reported, not hidden
            error = "%s: %s" % (type(exc).__name__, exc)
        played.append({"turn": idx, "input": player_input, "turn_id": tid,
                       "error": error, "seconds": round(time.time() - started, 1)})
        print("  beat %2d  %5.1fs  %s%s" % (
            idx + 1, played[-1]["seconds"], player_input[:58],
            "  ERROR " + error[:70] if error else ""), flush=True)
    return played


def narration_by_turn(db, cid):
    rows = db.q(
        "SELECT s.turn_id, v.content FROM variants v "
        "JOIN steps s ON s.id = v.step_id "
        "JOIN turns t ON t.id = s.turn_id "
        "WHERE v.active=1 AND s.key='narrator' AND t.chat_id=? "
        "ORDER BY s.turn_id", (cid,)) or []
    prose = {}
    for row in rows:
        try:
            blob = json.loads(row["content"])
        except (TypeError, ValueError):
            continue
        if isinstance(blob, dict) and blob.get("prose"):
            prose.setdefault(row["turn_id"], str(blob["prose"]))
    return prose


def transcript(played, prose, rates):
    lines = [
        "# The Vale, played by a model",
        "",
        "Only the opening scene is authored. Every stage from the first beat",
        "on -- interpret, resolve, perception per perceiver, each character,",
        "the narrator, mapping, and the off-screen rungs -- is a real model",
        "call through `providers.chat_complete`, validated and repaired by",
        "`llm_quality` exactly as it would be for a paying user.",
        "",
        "The player's inputs are occasions, not instructions. Whether an",
        "occasion becomes a `courier_ops` entry or evaporates into prose is",
        "the measurement.",
        "",
        "---",
        "",
    ]
    for row in played:
        lines.append("### %d. %s" % (row["turn"] + 1, row["input"]))
        lines.append("")
        if row["error"]:
            lines.append("> **pipeline error:** `%s`" % row["error"][:200])
            lines.append("")
        text = prose.get(row["turn_id"])
        if text:
            lines.append(text)
            lines.append("")
    if rates:
        lines += ["---", "", "## What fired", "", "```", rates, "```", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="", help="where to write the artefacts")
    ap.add_argument("--capture", default="", help="dump stage payloads")
    ap.add_argument("--beats", type=int, default=0,
                    help="play only the first N beats (0 = all)")
    ap.add_argument("--fast", action="store_true",
                    help="free, very fast, and TRAINS ON WHAT IT IS SENT; "
                         "only ever for this synthetic world")
    ap.add_argument("--model", default="",
                    help="the model every role runs on (default %s)"
                         % MAIN_MODEL)
    ap.add_argument("--role-effort", action="append", default=[],
                    metavar="ROLE=LEVEL",
                    help="reasoning effort for ONE role, repeatable. Measured "
                         "2026-08-12: ~80-90% of director_resolve's output is "
                         "thinking trace while the final answer is ~1.2k "
                         "tokens, and wall clock is output/decode-rate -- so "
                         "this is the largest untested lever on the Director. "
                         "Whether less thinking costs resolution QUALITY is "
                         "the open question; measure it, do not assume it.")
    ap.add_argument("--orchestration", action="store_true",
                    help="dispatch the Director's scoped specialists "
                         "(default off, as in production)")
    ap.add_argument("--role-model", action="append", default=[],
                    metavar="ROLE=[PROVIDER:]MODEL",
                    help="override ONE role, repeatable. The point of the "
                         "specialist split is that a scoped task may not need "
                         "a reasoning model: `--role-model "
                         "director_social=some-lean-model` asks that question "
                         "one role at a time, and the llm_call log answers it "
                         "per role.")
    args = ap.parse_args()

    _require_scratch()
    import db as db_module

    db_module.init()
    main_model = args.model or (FAST_MAIN_MODEL if args.fast else MAIN_MODEL)
    perception_model = (FAST_PERCEPTION_MODEL if args.fast
                        else PERCEPTION_MODEL)
    if args.fast:
        print("--fast: %s is free and TRAINS ON ITS INPUT. Only the engine's\n"
              "        own prompts and an invented valley are sent."
              % FAST_MAIN_MODEL, flush=True)
    models = seed_providers(db_module, main_model=main_model,
                            perception_model=perception_model)
    # Per-role overrides, applied after the uniform seed so the baseline is
    # always "one model everywhere" and each override is a single named
    # departure from it -- which is what makes a per-role result attributable.
    if args.role_model:
        import json as _json
        for pair in args.role_model:
            role, _, model = pair.partition("=")
            role, model = role.strip(), model.strip()
            if not role or not model:
                raise SystemExit("--role-model wants ROLE=MODEL, got %r" % pair)
            if role not in models:
                raise SystemExit(
                    "unknown role %r; known: %s"
                    % (role, ", ".join(sorted(models))))
            # `ROLE=openrouter:x-ai/grok-4.20` moves the role to another
            # PROVIDER as well as another model. The specialists are the
            # roles worth doing this to: their sheets are 0.7-4.6k, so a
            # metered model is cheap there in a way it is not for the prose
            # author reading nine thousand tokens a beat.
            prov_name, _, bare = model.rpartition(":")
            if prov_name:
                row = db_module.q("SELECT id FROM providers WHERE name=?",
                                  (prov_name,), one=True)
                if not row:
                    raise SystemExit(
                        "--role-model names provider %r, which this run did "
                        "not seed (set its API key in the environment)"
                        % prov_name)
                models[role] = {"provider": row["id"], "model": bare}
                print("  role override: %s -> %s on %s"
                      % (role, bare, prov_name), flush=True)
            else:
                models[role] = {"provider": models[role]["provider"],
                                "model": model}
                print("  role override: %s -> %s" % (role, model), flush=True)
        db_module.set_setting("agent_models", _json.dumps(models))
    print("models: %s | perception: %s | embeddings: %s" % (
        main_model, perception_model,
        (models.get("embeddings") or {}).get("model") or "off"), flush=True)
    if args.role_effort:
        import json as _json
        efforts = {}
        for pair in args.role_effort:
            role, _, level = pair.partition("=")
            role, level = role.strip(), level.strip()
            if not role or not level:
                raise SystemExit("--role-effort wants ROLE=LEVEL, got %r" % pair)
            efforts[role] = level
            print("  reasoning effort: %s -> %s" % (role, level), flush=True)
        db_module.set_setting("reasoning_effort", _json.dumps(efforts))

    if args.orchestration:
        db_module.set_setting("director_orchestration", "1")
        print("  director orchestration: ON", flush=True)
    author = QuestAuthor()
    author.capture_dir = args.capture
    install(author)

    cid = build_story(db_module)
    inputs = BEATS[:args.beats] if args.beats else BEATS
    print("playing %d beats" % len(inputs), flush=True)
    played = play(db_module, cid, inputs)

    # The off-screen rungs are daemon threads; give them a moment to land.
    time.sleep(8)

    print()
    errors = [p for p in played if p["error"]]
    print()
    print("beats played : %d" % len(played))
    print("errors       : %d" % len(errors))
    for row in errors[:5]:
        print("   beat %d: %s" % (row["turn"] + 1, row["error"][:140]))

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        rates = ""
        try:
            import subprocess
            rates = subprocess.run(
                [sys.executable, "tools/fire_rates.py"],
                capture_output=True, text=True, timeout=300,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ).stdout
        except Exception:                      # noqa: BLE001 - artefact only
            rates = ""
        with open(os.path.join(args.out, "transcript.md"), "w") as fh:
            fh.write(transcript(played, narration_by_turn(db_module, cid),
                                rates))
        from chat_archive import ChatArchiveService
        export = ChatArchiveService.export_chat(None, cid)
        export["checkpoints"] = []
        with open(os.path.join(args.out, "story.json"), "w") as fh:
            json.dump(export, fh, indent=1, default=str)
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
