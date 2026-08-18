"""Regression tests for application-level symbol imports."""

def test_branch_lorebook_restore_helper_is_imported():
    from web import app
    from mind import memory

    assert app.restore_lorebook_links is memory.restore_lorebook_links