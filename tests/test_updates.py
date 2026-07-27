import updates


def test_git_repo_check_rejects_an_unrelated_parent_checkout(
    monkeypatch, tmp_path
):
    parent = tmp_path / "unrelated-checkout"
    install = parent / "copied-install"
    install.mkdir(parents=True)

    monkeypatch.setattr(updates, "REPO_ROOT", str(install))
    monkeypatch.setattr(
        updates, "_git", lambda *args, **kwargs: str(parent)
    )

    assert updates._is_git_repo() is False


def test_git_repo_check_accepts_the_install_as_checkout_root(
    monkeypatch, tmp_path
):
    install = tmp_path / "checkout"
    install.mkdir()

    monkeypatch.setattr(updates, "REPO_ROOT", str(install))
    monkeypatch.setattr(
        updates, "_git", lambda *args, **kwargs: str(install)
    )

    assert updates._is_git_repo() is True


def test_git_repo_check_handles_git_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise updates.GitError("not a checkout")

    monkeypatch.setattr(updates, "_git", fail)

    assert updates._is_git_repo() is False


def test_check_updates_returns_an_error_when_branch_lookup_fails(monkeypatch):
    monkeypatch.setattr(updates, "_is_git_repo", lambda: True)

    def fail():
        raise updates.GitError("HEAD is missing")

    monkeypatch.setattr(updates, "_current_branch", fail)

    assert updates.check_updates() == {
        "ok": False,
        "error": "HEAD is missing",
    }


def test_install_refuses_dirty_tree_before_contacting_remote(monkeypatch):
    monkeypatch.setattr(updates, "_is_git_repo", lambda: True)
    monkeypatch.setattr(updates, "_current_branch", lambda: "main")
    monkeypatch.setattr(updates, "_short_status", lambda: " M updates.py")

    def unexpected_remote_lookup(branch):
        raise AssertionError("dirty installs must not contact the remote")

    monkeypatch.setattr(updates, "_upstream_ref", unexpected_remote_lookup)

    result = updates.install_updates()

    assert result["ok"] is False
    assert "local changes" in result["error"]
