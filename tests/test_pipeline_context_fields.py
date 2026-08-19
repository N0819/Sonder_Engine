"""The declared-field set of PipelineContext, and what depends on it.

`runtime.STEP_HANDLERS`, `schemas.SCHEMA_MAP` and `PipelineContext`'s fields
are three hand-kept lists that must agree; `agents/README.md` step 5 makes the
field mandatory as soon as a later stage reads the output. The two storage
mechanisms are NOT interchangeable: `__contains__` answers
`getattr(...) is not None` for a declared field but `key in _extra` for
anything else, so an undeclared step whose handler returned `None` passes
`_assert_plan_materialized` and a declared one does not.
"""

from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx():
    return PipelineContext(
        chat=ChatData(id=1, name="c", persona_id=None, lorebook_id=None,
                      scenario="", created=0.0),
        turn=TurnData(id=1, chat_id=1, idx=1, player_input="", created=0.0),
        cast=[], input="",
    )


def _declared(name):
    return name in PipelineContext.__dataclass_fields__


def test_every_in_package_step_key_has_a_declared_field():
    # Dynamic `character:<id>`/`reaction:<id>` steps have their own maps, and
    # `ext:<id>:<key>` steps belong to third parties -- but every step key this
    # repo plans is a name the context must carry typed.
    from agents import runtime

    missing = [key for key in runtime.STEP_HANDLERS
               if not key.startswith(("character:", "ext:"))
               and not _declared(key)]
    assert missing == []


def test_a_step_that_returned_none_is_not_materialized():
    ctx = _ctx()
    for key in ("background_react", "commit"):
        ctx[key] = None
        assert key not in ctx, (
            f"{key} set to None must read as ABSENT, the way every other "
            "declared stage does")


def test_no_declared_name_can_ever_reach_the_extra_dict():
    # `__setitem__` routes any key `hasattr` answers for to `setattr`, so the
    # two stores cannot both hold a declared name -- which is what made
    # `get`'s underscore-prefixed `_extra` fallback unreachable. Underscore
    # names are the interesting case: all five of them are declared fields.
    ctx = _ctx()
    for name in PipelineContext.__dataclass_fields__:
        if name == "_extra":
            continue
        ctx[name] = {"probe": name}
        assert getattr(ctx, name) == {"probe": name}
    assert ctx._extra == {}


def test_step_output_round_trips_through_the_declared_field():
    ctx = _ctx()
    ctx["background_react"] = {"fired": True}
    ctx["commit"] = {"summary": "done"}
    assert ctx.background_react == {"fired": True}
    assert ctx.commit == {"summary": "done"}
    assert ctx.get("background_react") == {"fired": True}
    assert ctx["commit"] == {"summary": "done"}
    assert "background_react" not in ctx._extra
    assert "commit" not in ctx._extra
