"""`_scrub_invented_dialogue` reads the pack's quote marks once per view.

The clause-boundary walk looked `_QUOTE_CHARS` up once per CHARACTER of the
view (agents_common audit, Efficiency 2: 0.94 µs a lookup, ~3 ms per
3,000-character view, per observer, per composer pass). The answer cannot
change inside one call, so it is read once.
"""

from __future__ import annotations

from agents import common_scrubs


def test_the_quote_marks_are_read_once_per_view(monkeypatch):
    real = common_scrubs._ling
    reads = []

    def counting(name):
        reads.append(name)
        return real(name)

    monkeypatch.setattr(common_scrubs, "_ling", counting)
    view = ('The rain keeps on. "We should go," she says. ' * 60).strip()
    out, dropped = common_scrubs._scrub_invented_dialogue(
        view, ["We should go,"])
    assert out == view and dropped == []
    assert reads.count("_QUOTE_CHARS") == 1, reads.count("_QUOTE_CHARS")


def test_an_invented_line_is_still_dropped():
    out, dropped = common_scrubs._scrub_invented_dialogue(
        'The rain keeps on. "Nobody said this," she says. The door shuts.',
        ["We should go."])
    assert out == "The rain keeps on. The door shuts.", out
    assert dropped == ['"Nobody said this,"']
