"""Static regression checks for browser-global async state ownership.

The frontend deliberately has no bundler or browser-test dependency. These
checks pin the small sequencing guards that prevent delayed fetches and mutable
navigation state from crossing story/provider boundaries.
"""

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
