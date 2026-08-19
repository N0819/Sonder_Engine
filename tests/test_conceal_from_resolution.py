"""`conceal_from` is an absolute exclusion list, so failing to read it must
not deliver the line.

`_conceal_from_targets_observer` resolves an exclusion entry against every
handle the observer answers to -- numeric id, string id, display name, uid,
alias -- because the speaker authored it against whichever handle they knew.
That resolution went through `character_scene_keys`, wrapped in a bare
`except Exception: keys = set()`: on a sheet it could not read, every name,
uid and alias form vanished and only the numeric-id form survived. A
name-authored exclusion then matched nothing, the guard answered "this
observer is not excluded", and the concealed line was delivered verbatim to
the one mind it was concealed from -- into its next character step, its
outcome view and its durable memory.

Fail-open on a firewall path, with no warning: exactly the shape AGENTS.md
§ Information boundaries #4 describes, where the thing that would have
announced the leak is the thing that did not run.

The class, stated in engine vocabulary: an exclusion the engine cannot
resolve is not an exclusion that does not apply. When the handles cannot be
read the guard cannot prove this observer is NOT the excluded party, and
withholding one line costs a delivery while delivering it costs the
firewall.
"""

from __future__ import annotations

from core import pipeline_context
from story.character_schema import character_name, default_character_data

from agents.common import _conceal_from_targets_observer, character_scene_keys


def _unreadable_sheet(name):
    """A sheet whose identity handles cannot be enumerated.

    One member of the class, not the specification: `aliases` here is a
    scalar rather than a list, so `character_scene_keys` raises while
    `character_name` reads the sheet perfectly well -- which is why the
    observer is still a live, co-present perceiver in the call where the
    exclusion is being resolved.
    """
    sheet = default_character_data(name)
    sheet["identity"]["aliases"] = 5
    return sheet


# --- the premise -----------------------------------------------------------

def test_the_premise_a_sheet_can_break_the_handles_and_not_the_name():
    sheet = _unreadable_sheet("Kael")
    assert character_name(sheet) == "Kael"
    try:
        character_scene_keys(sheet)
    except Exception:
        return
    raise AssertionError("the handle enumeration no longer fails on this "
                         "sheet; pick another member of the class")


# --- the guard itself ------------------------------------------------------

def test_a_name_authored_exclusion_holds_when_the_handles_cannot_be_read():
    """The leak, at the function that produced it."""
    assert _conceal_from_targets_observer(
        ["Kael"], 7, _unreadable_sheet("Kael"))


def test_an_unreadable_sheet_excludes_whoever_the_entry_named():
    """It is not a name-matching failure that is being repaired -- the guard
    cannot tell WHO the entry names, so it cannot clear anybody."""
    assert _conceal_from_targets_observer(
        ["Someone Else"], 7, _unreadable_sheet("Kael"))


def test_an_id_authored_exclusion_still_matches_on_an_unreadable_sheet():
    assert _conceal_from_targets_observer([7], 7, _unreadable_sheet("Kael"))


def test_a_readable_sheet_still_clears_an_observer_nobody_excluded():
    """The negative control: the fix must subtract only where it cannot see."""
    assert not _conceal_from_targets_observer(
        ["Kael"], 7, default_character_data("Mara"))


def test_a_readable_sheet_still_matches_by_name():
    assert _conceal_from_targets_observer(
        ["Kael"], 7, default_character_data("Kael"))


def test_an_empty_exclusion_list_excludes_nobody_even_unreadably():
    """`conceal_from` empty means the line is not concealed from anyone; an
    unreadable sheet must not invent an exclusion that was never authored."""
    assert not _conceal_from_targets_observer(
        [], 7, _unreadable_sheet("Kael"))


def test_the_unreadable_sheet_is_reported():
    """A guard that subtracts silently is the next invisible defect."""
    seen = []
    token = pipeline_context.current_warning_sink.set(seen.append)
    try:
        _conceal_from_targets_observer(["Kael"], 7, _unreadable_sheet("Kael"))
    finally:
        pipeline_context.current_warning_sink.reset(token)
    assert any("conceal_from" in line for line in seen), seen


# --- why there is no end-to-end test here ---------------------------------
#
# The sole production caller is agents/loops.py's micro-perception sweep, and
# forty lines above the exclusion check it resolves the SAME handles for the
# SAME sheet through `character_room` -- with no guard at all. So every sheet
# that would trip the fail-open branch takes the whole turn down first, and
# the delivery this guard was leaking cannot currently be reached through the
# pipeline: the fail-open is latent, not live.
#
# It is repaired anyway, and on its own terms. A firewall floor that holds
# only because an unrelated function happens to crash before it is not a
# floor; it is one refactor away from being a leak, and the guard is exported
# through the `agents` facade for callers that have no such accident.
#
# `character_scene_keys` not being total is a separate defect (it takes down
# `character_room`, `character_name`'s siblings and anything else reading an
# authored sheet), and belongs to whoever owns that class -- not here, where
# it would hide the guard this file is about.
