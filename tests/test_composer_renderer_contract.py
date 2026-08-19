"""A pack adapter that returned the wrong shape killed the turn it rendered.

`render_view` already treats a language adapter as untrusted: it wraps the
call in try/except so that "a malformed pack must cost wording, never the
whole beat", and falls through to the English reference renderer. The guard
covered only the RAISE. An adapter that returned successfully with something
that is not a `RenderedView` sailed past it, and the caller
(`perception._composer_finish_observer`) then read `.text`, `.standing_keys`
and `.described` off it with no guard at all -- outside the try, one stage
after the only place that was watching.

The failure a pack is most likely to produce is exactly that one: returning
a dict, or a tuple, or the text alone. So the contract is checked where the
tolerance already lives.
"""

import pytest

from agents.composer import Percept, RenderedView, render_view


def _percepts():
    return [Percept(
        kind="speech", channel="hearing", source_label="Reya",
        fidelity="full",
        data={"body": "Mind the rail.", "level": "full",
              "volume": "normal", "can_see": True},
        salience=0.8, order_key=0, dedupe_key="speech:rail",
    )]


class _RaisingRenderer:
    def render_view(self, percepts, **kw):
        raise RuntimeError("pack exploded")


class _DictRenderer:
    """The shape a pack gets wrong first: a plain mapping."""

    def render_view(self, percepts, **kw):
        return {"text": "レヤ「手すりに気をつけて」", "spans": []}


class _TextRenderer:
    """The other one: the rendered string, without the ledger fields."""

    def render_view(self, percepts, **kw):
        return "レヤ「手すりに気をつけて」"


class _GoodRenderer:
    def render_view(self, percepts, **kw):
        return RenderedView(text="rendered by the pack", spans=[],
                            standing_keys=set(), described=set())


def test_a_raising_adapter_falls_back_to_english():
    """The half that already worked, pinned so the new check cannot cost it."""
    out = render_view(_percepts(), renderer=_RaisingRenderer())
    assert isinstance(out, RenderedView)
    assert "Mind the rail." in out.text


@pytest.mark.parametrize("renderer", [_DictRenderer(), _TextRenderer()])
def test_an_adapter_returning_the_wrong_shape_falls_back(renderer):
    out = render_view(_percepts(), renderer=renderer)
    assert isinstance(out, RenderedView), (
        f"a wrong-shaped adapter return reached the caller: {out!r}")
    assert "Mind the rail." in out.text


def test_a_well_formed_adapter_is_used_unchanged():
    """The tolerance must not become a rewrite. A pack that answers correctly
    still owns the wording."""
    out = render_view(_percepts(), renderer=_GoodRenderer())
    assert out.text == "rendered by the pack"
