"""Host switches: what the engine does, what the API reports, what the host sees.

A host setting has three faces -- the gate that decides, the route that reports
it, and the control that changes it -- and nothing in the tree makes them agree.
Each of these tests pins one place they were measured to disagree.

Two failure shapes recur, and both are silent:

  * **Two readings of one row.** A route re-derives a setting's truthiness with
    its own expression instead of calling the gate. `"" != "0"` is True and
    `"" in ("1", "on", ...)` is False, so the two answers part company on
    exactly the case that matters -- a fresh install where nothing was ever
    written.
  * **A control the copy names and the browser does not have.** Help text that
    says "switch it on in X" is a promise; if X has no such switch, the setting
    is unreachable and the host has no way to learn that.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_JS = (ROOT / "static/js/settings.js").read_text(encoding="utf-8")


class TestAutoPromoteIsOneAnswer:
    """FRONTEND-2. The gate is `persist/commit_background._auto_promote_enabled`."""

    def test_an_unset_setting_reads_off_everywhere(self, temp_db):
        from persist.commit_background import _auto_promote_enabled
        from web import app

        assert _auto_promote_enabled() is False
        assert app.get_auto_promote()["enabled"] is False
        assert app.bootstrap()["auto_promote"] is False

    def test_switching_it_on_reads_on_everywhere(self, temp_db):
        from persist.commit_background import _auto_promote_enabled
        from web import app

        app.set_auto_promote({"enabled": True})

        assert _auto_promote_enabled() is True
        assert app.get_auto_promote()["enabled"] is True
        assert app.bootstrap()["auto_promote"] is True

    def test_switching_it_off_reads_off_everywhere(self, temp_db):
        from persist.commit_background import _auto_promote_enabled
        from web import app

        app.set_auto_promote({"enabled": True})
        app.set_auto_promote({"enabled": False})

        assert _auto_promote_enabled() is False
        assert app.get_auto_promote()["enabled"] is False
        assert app.bootstrap()["auto_promote"] is False

    def test_the_switch_the_dialogue_panel_promises_exists(self):
        """The per-story dial's help says promotion "has to be switched on
        globally in ⚙ API". That sentence had no control behind it."""
        assert "switched on globally in ⚙ API" in SETTINGS_JS
        assert '"PUT", "/api/auto_promote"' in SETTINGS_JS
        assert "S.boot.auto_promote" in SETTINGS_JS
