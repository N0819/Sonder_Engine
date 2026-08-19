"""Static regression checks for browser-global async state ownership.

The frontend deliberately has no bundler or browser-test dependency. These
checks pin the small sequencing guards that prevent delayed fetches and mutable
navigation state from crossing story/provider boundaries.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "static/js/chat.js").read_text(encoding="utf-8")
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
COMPONENTS = (ROOT / "static/js/components.js").read_text(encoding="utf-8")
LOREBOOKS = (ROOT / "static/js/lorebooks.js").read_text(encoding="utf-8")
SETTINGS = (ROOT / "static/js/settings.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def test_open_chat_only_publishes_the_latest_navigation():
    block = _between(CHAT, "async function openChat(id)", "function renderFrameBar()")
    guard = "if (loadSeq !== _chatLoadSeq || S.chatId !== id) return false;"

    assert "const loadSeq = ++_chatLoadSeq;" in block
    assert block.count(guard) >= 2  # stale success and stale failure
    assert block.index(guard, block.index("chat = await api")) < block.index("S.chat = chat;")


def test_same_story_refresh_preserves_a_valid_selected_frame():
    block = _between(CHAT, "async function openChat(id)", "function renderFrameBar()")

    switch_branch = _between(block, "if (switching) {", "let chat;")
    assert "closeAllModals();" in switch_branch
    assert "const frameStillExists = (chat.frames || []).some(" in block
    assert "if (switching || !frameStillExists) S.currentFrameId = null;" in block
    assert "S.currentFrameId = null; // always reopen viewing the present" not in block


def test_stop_uses_the_context_captured_by_the_active_stream():
    stream = _between(CHAT, "async function runStream(", "// Rerolling/resuming/")
    abort = _between(CHAT, "async function abortActiveRun()", "async function runStream(")
    stop = _between(APP, '$("#stop").onclick', '$("#b-nsfw").onclick')

    assert "_activeRun = run;" in stream
    assert "if (_activeRun === run) _activeRun = null;" in stream
    assert "/api/chats/${run.chatId}/abort${query}" in abort
    assert "run.frameId" in abort
    assert "abortActiveRun();" in stop
    assert "S.chatId" not in stop
    assert "S.currentFrameId" not in stop


def test_model_catalogue_only_applies_to_the_latest_selected_provider():
    picker = _between(COMPONENTS, "function modelCombobox(", "return { psel, mwrap")

    assert "const seq = ++loadSeq;" in picker
    guard = 'if (seq !== loadSeq || String(psel.value) !== String(pid)) return;'
    assert guard in picker
    assert picker.index(guard) < picker.index("models = loaded;")
    assert "loadSeq++;" in picker  # clearing the provider invalidates a pending load
    assert "await load(+psel.value);\n    } else {\n      showDD();" in picker


def test_the_model_catalogue_is_primed_without_opening_the_dropdown():
    """Opening API settings must not expand a dozen model lists nobody clicked.

    `modelCombobox` ends by loading the catalogue for whichever provider is
    already saved, so the first focus is instant. Loading and SHOWING were the
    same act, so that priming call opened the dropdown as a side effect --
    and Agent models builds one combobox per role, so opening the menu
    expanded every one of them at once, each covering the rows beneath it.

    Asserted on the source the way the sibling guards here are: the behaviour
    is a browser one, and the browser tier is optional, so the invariant that
    can be checked in the default tier is that the priming call passes
    `open: false` and that `load` honours it.
    """
    picker = _between(COMPONENTS, "function modelCombobox(", "return { psel, mwrap")

    assert "if (cp) load(+cp, { open: false });" in picker
    assert "async function load(pid, { open = true } = {})" in picker
    # Both places load() reveals the panel are behind the flag.
    assert "if (open) showDD();" in picker
    assert "if (open) {\n      dd.innerHTML = \"\"; dd.style.display = \"block\";" in picker
    # And focus still opens it, which is the whole point of having a dropdown.
    assert "minput.onfocus" in picker


def test_modal_ownership_uses_a_unique_current_owner_token():
    guard = _between(COMPONENTS, "function modalOwnership(", "function closeModal()")

    assert "const ownerToken = S.modalOwnerToken;" in guard
    assert "S.modalOwnerToken === ownerToken" in guard
    assert 'body === $("#modalbody")' in guard
    assert '!$("#modal").classList.contains("hidden")' in guard


def test_stacked_parent_async_ownership_is_restored_after_child_closes():
    opening = _between(COMPONENTS, "function modal(title", "function modalOwnership(")
    closing = _between(COMPONENTS, "function closeModal()", "function closeAllModals()")

    assert "ownerToken: S.modalOwnerToken" in opening
    assert "S.modalOwnerToken = ++S.modalToken;" in opening
    assert "S.modalToken++;" in closing  # allocator stays monotonic on unwind
    assert "S.modalOwnerToken = prev.ownerToken;" in closing
    assert closing.index("S.modalToken++;") < closing.index(
        "S.modalOwnerToken = prev.ownerToken;"
    )
    assert "S.modalOwnerToken = null;" in closing  # closing the root rejects it
    assert "S.modalToken = prev.ownerToken" not in closing


def test_relationship_response_cannot_overwrite_a_newer_modal():
    block = _between(CHAT, "async function relationshipModal(", "// ---- Memory browser")

    assert "const chatId = boundChatId ?? S.chatId;" in block
    assert block.count("S.chatId !== chatId") >= 2
    assert "/api/chats/${chatId}/characters/${p.id}/relationships" in block
    assert "/api/chats/${S.chatId}" not in block
    assert "const ownsModal = modalOwnership(body);" in block
    assert block.count("if (!ownsModal()) return;") >= 2
    assert block.index("if (!ownsModal()) return;", block.index("rels = await api")) < block.index(
        'body.innerHTML = "";', block.index("rels = await api")
    )


def test_lore_workspace_checks_selection_and_modal_ownership_after_await():
    block = _between(
        LOREBOOKS,
        "async function renderLoreWorkspaceBody(selectedId)",
        "async function openLoreWorkspace(selectedId)",
    )

    assert "const ownsModal = modalOwnership(body);" in block
    assert "if (!ownsModal() || loreUI.selectedId !== wanted)" in block
    assert "if (ownsModal() && loreUI.selectedId === wanted)" in block
    assert "if (loreUI.renderOwner === ownsModal)" in block


def test_update_check_and_install_discard_stale_modal_results():
    check = _between(SETTINGS, "function renderUpdateChecking(b)", "function renderUpdateError(")
    install = _between(SETTINGS, "function runUpdateInstall(b, btn)", "function renderUpdateDone(")

    assert "const ownsModal = modalOwnership(b);" in check
    assert check.count("if (!ownsModal()) return;") == 2
    assert "const ownsModal = modalOwnership(b);" in install
    assert install.count("if (!ownsModal()) return;") == 2


def test_story_tool_dialogs_capture_one_chat_for_reads_and_writes():
    cases = [
        ('$("#b-world").onclick', '$("#b-attire").onclick', "world"),
        ('$("#b-attire").onclick', "// Genre & style", "attire"),
        ('$("#b-style").onclick', '$("#b-dlg").onclick', "style_guide"),
        ('$("#b-dlg").onclick', "// The Cast modal", "dialogue_config"),
    ]
    for start, end, endpoint in cases:
        block = _between(SETTINGS, start, end)
        assert "const chatId = S.chatId;" in block
        assert "if (S.chatId !== chatId) return;" in block
        assert f"/api/chats/${{chatId}}/{endpoint}" in block
        assert "/api/chats/${S.chatId}" not in block


def test_cast_dialog_threads_its_captured_chat_through_all_tabs():
    entry = _between(SETTINGS, '$("#b-cast").onclick', "// ---- Condition tab")
    tabs = _between(SETTINGS, "function renderLorebooksTab(", "// ---- API connections")
    locations = _between(SETTINGS, "async function hydrateCastLocations(", "function renderLorebooksTab(")

    assert "const chatId = S.chatId;" in entry
    assert "if (S.chatId !== chatId) return;" in entry
    assert ".render(d, content, chatId);" in entry
    assert "function renderCastTab(d, b, chatId)" in entry
    assert "onclick: () => relationshipModal(p, chatId)" in entry
    assert "/api/chats/${S.chatId}" not in entry

    assert "async function hydrateCastLocations(slots, sceneSlot, chatId)" in locations
    assert "function castRoomSelect(charId, person, rooms, chatId)" in locations
    assert "/api/chats/${S.chatId}" not in locations

    for signature in (
        "function renderLorebooksTab(d, b, chatId)",
        "function renderMultiplayerTab(d, b, chatId)",
        "function renderFramesTab(d, b, chatId)",
        "function renderFramesListPanel(d, chatId)",
        "function renderPersonaStationingPanel(chatId)",
        "function renderParadoxPanel(chatId)",
        "function renderBackgroundPresencesPanel(chatId)",
        "function renderGuestInvitePanel(chatId)",
        "function renderInsightsTab(d, b, chatId)",
    ):
        assert signature in tabs
    assert "/api/chats/${S.chatId}" not in tabs
    assert '"/api/chats/" + S.chatId' not in tabs


def test_private_history_discards_switched_reads_and_saves_to_bound_chat():
    character = _between(CHAT, "async function chatPH(", "async function personaPH(")
    persona = CHAT[CHAT.index("async function personaPH("):]

    for block in (character, persona):
        assert "const chatId = boundChatId ?? S.chatId;" in block
        assert block.count("S.chatId !== chatId") >= 2
        assert "/api/chats/${chatId}" in block
        assert "/api/chats/${S.chatId}" not in block


BACKDROPS = (ROOT / "static/js/backdrops.js").read_text(encoding="utf-8")
AMBIENCE = (ROOT / "static/js/ambience.js").read_text(encoding="utf-8")


def test_freshness_is_a_property_of_the_turn_not_a_one_shot_flag():
    """A boolean here was spent by the observer pass that READ it, while the
    work it authorised -- commissioning a picture at once rather than after a
    two-second dwell -- was deferred by BD_SETTLE_MS. renderChat guarantees a
    second pass inside that window (it re-asserts its scroll in a rAF, because
    content-visibility makes the first scrollHeight an estimate), which then
    reported a brand-new turn as one being scrolled past.
    """
    block = _between(CHAT, "function observeVisibleTurn(", "async function openChat(id)")

    assert "let _freshTurnPending" not in CHAT       # the one-shot is gone
    assert "let _freshTurnId = null;" in CHAT
    # Named where the id first exists, which is not the run's own finally.
    assert "if (_freshRunPending) {" in block
    assert "_freshTurnId = newestTurnId;" in block
    # Released by the reader settling elsewhere, never by the act of reading it.
    assert "if (bestTurnId !== _freshTurnId) _freshTurnId = null;" in block
    assert "if (fresh) _freshTurnId = null;" not in block


def test_a_repeat_pass_over_one_turn_does_not_restart_the_commission_clocks():
    """Both scene layers restarted a two-second dwell on every notification,
    and several per render are not the reader moving: the rAF re-scroll, and
    the reflow clearBackdrop() causes by stripping padding, border and
    max-width off every .prose. Only a room with no picture yet could be lost
    to it -- a drawn room is served by the quick pass and never dwells.
    """
    for source, state, fn in ((BACKDROPS, "BD", "function backdropOnVisibleTurn("),
                              (AMBIENCE, "AMB", "function ambienceOnVisibleTurn(")):
        block = source[source.index(fn):source.index("\n}", source.index(fn))]
        assert "if (turnId === %s.pendingTurn) return;" % state in block
        assert "%s.pendingTurn = turnId;" % state in block
        # And a re-render, which cancels the clocks, must let the same turn arm
        # them again rather than reading as a repeat.
        assert "%s.pendingTurn = null;" % state in source


def test_boot_reports_a_language_pack_the_server_could_not_use():
    """`/api/bootstrap` deliberately survives a malformed pack and returns the
    reason in `language_error` -- "the host needs to know a pack they installed
    is not being used, and why". Nothing read it, so the host got English and
    silence. Once per session: `boot()` reruns on every import and save.
    """
    block = _between(APP, "async function boot()", "$$(\"#tabs button\")")

    assert "S.boot.language_error" in block
    assert "toast(S.boot.language_error" in block
    assert "let languagePackErrorReported = false;" in APP
    assert "languagePackErrorReported = true;" in block


def test_every_chat_scoped_toolbar_button_is_disabled_without_a_chat():
    """The membership rule is the handler's own guard, so derive the set from
    it rather than trusting a hand-kept list. `#b-style` had the guard and was
    missing from the list, so with no story open it stayed lit and did nothing
    -- the silent dead click the disabling exists to eliminate."""
    guarded = set(re.findall(
        r'\$\("(#b-[\w-]+)"\)\.onclick = async \(\) => \{\s*\n\s*if \(!S\.chatId\) return;',
        SETTINGS))
    assert guarded, "no chat-scoped handlers found -- the pattern moved"

    block = _between(CHAT, "function updateChatScopedButtons()", "function renderChat()")
    listed = set(re.findall(r'"(#b-[\w-]+)"', block))
    assert listed == guarded, f"listed {sorted(listed)} vs guarded {sorted(guarded)}"


def test_every_engine_plan_step_has_a_friendly_progress_label():
    """The progress line exists so "a long-running turn never looks like
    nothing is happening, without requiring anyone to know what
    `perception_outcome` means". A step missing from the table falls through to
    the technical label, which is the one thing it was built to avoid --
    `narrator_extra` did, on exactly the stage a multiplayer chat spends its
    time in. Read from the handler registry so a fifteenth stage cannot be
    added to the engine alone.
    """
    import ast

    tree = ast.parse((ROOT / "agents/runtime.py").read_text(encoding="utf-8"))
    handlers = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "STEP_HANDLERS" for t in node.targets)):
            handlers = {k.value for k in node.value.keys}
    assert handlers, "STEP_HANDLERS not found in agents/runtime.py"

    block = _between(CHAT, "const FRIENDLY_STEP_LABELS = {", "const FRIENDLY_SUBAGENTS")
    labelled = set(re.findall(r"^  (\w+):", block, re.MULTILINE))
    assert not handlers - labelled, \
        f"plan steps with no friendly label: {sorted(handlers - labelled)}"


def test_the_global_error_net_catches_synchronous_throws_too():
    """The rejection listener covers every handler that awaits. A handler that
    throws before its first await produced the identical "clicking does
    nothing" and reached nothing -- the failure mode the net was written to
    eliminate, surviving in the half nobody installed."""
    assert 'window.addEventListener("unhandledrejection"' in APP
    assert 'window.addEventListener("error"' in APP
    net = APP[APP.index('window.addEventListener("error"'):]
    # A failed script/image load has no usable message; it must not become a
    # toast the reader can do nothing with.
    assert "if (!message) return;" in net
    # And whatever already toasted itself must not toast twice.
    assert "__handled" in net
