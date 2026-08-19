"""MASTER-009: an archive from a NEWER engine must be refused, not
silently truncated.

The archive model declares ``version: int = 1`` with ``extra = "allow"``,
the exporter writes the current version, and import never read the field
at all -- so a version-5 archive imported 200 OK while every table this
binary does not enumerate was dropped on the floor. The module's own
comment records that exact failure keeping ``stations`` inert for 45
scenes. The check must run BEFORE the transaction opens: a refusal is not
allowed to half-write a chat.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from persist import chat_archive
from web import app


def _minimal_archive(version):
    return {
        "data": {
            "version": version,
            "chat": {
                "name": "From the future",
                "persona_id": None,
                "scenario": "",
            },
        }
    }


def test_the_exporter_and_the_constant_agree():
    """The wire version must come from the named constant, so bumping one
    cannot silently leave the other behind."""
    import inspect

    assert isinstance(chat_archive.ARCHIVE_VERSION, int)
    source = inspect.getsource(chat_archive.ChatArchiveService.export_chat)
    assert '"version": ARCHIVE_VERSION' in source


def test_a_newer_archive_is_refused_naming_both_versions(temp_db):
    newer = chat_archive.ARCHIVE_VERSION + 1
    with pytest.raises(HTTPException) as exc:
        app.chat_import(_minimal_archive(newer))
    assert exc.value.status_code == 400
    assert str(newer) in exc.value.detail
    assert str(chat_archive.ARCHIVE_VERSION) in exc.value.detail


def test_a_refused_import_writes_nothing(temp_db):
    from core.db import q

    before = q("SELECT COUNT(*) AS n FROM chats", one=True)["n"]
    with pytest.raises(HTTPException):
        app.chat_import(_minimal_archive(chat_archive.ARCHIVE_VERSION + 1))
    after = q("SELECT COUNT(*) AS n FROM chats", one=True)["n"]
    assert after == before


def test_the_current_version_still_imports(temp_db):
    imported = app.chat_import(_minimal_archive(chat_archive.ARCHIVE_VERSION))
    assert imported["name"] == "From the future (import)"


def test_a_versionless_legacy_archive_still_imports(temp_db):
    payload = _minimal_archive(1)
    del payload["data"]["version"]
    imported = app.chat_import(payload)
    assert imported["name"] == "From the future (import)"
