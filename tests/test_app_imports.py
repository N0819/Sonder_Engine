"""Regression tests for application-level symbol imports."""

def test_branch_lorebook_restore_helper_is_imported():
    import app
    import memory

    assert app.restore_lorebook_links is memory.restore_lorebook_links