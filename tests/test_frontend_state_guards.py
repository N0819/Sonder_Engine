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
WORLD_BROWSER = (ROOT / "static/js/world_browser.js").read_text(encoding="utf-8")
WRITERS_ROOM = (ROOT / "static/js/writers_room.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "language_packs/en/ui.json").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def test_open_chat_only_publishes_the_latest_navigation():
    block = _between(CHAT, "async function openChat(id", "function renderFrameBar()")
    guard = "if (loadSeq !== _chatLoadSeq || S.chatId !== id) return false;"

    assert "const loadSeq = ++_chatLoadSeq;" in block
    assert block.count(guard) >= 2  # stale success and stale failure
    assert block.index(guard, block.index("chat = await api")) < block.index("S.chat = chat;")


def test_same_story_refresh_preserves_a_valid_selected_frame():
    block = _between(CHAT, "async function openChat(id", "function renderFrameBar()")

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


def test_the_transcript_is_only_spliced_after_an_appended_beat():
    """`?since_turn_id=` is sound because a transcript grows at the END
    (review 2026-09-07, C22). Two conditions carry that, and neither shows up
    as a failure the next reader would connect to this: splice a reply into a
    page that does not hold the turn it is measured from and turns go missing;
    splice after a reroll and the page keeps showing prose the story replaced.
    """
    block = _between(CHAT, "async function openChat(id", "function renderFrameBar()")
    stream = _between(CHAT, "async function runStream(", "// Rerolling/resuming/")

    # Asked for only when this page really holds that turn, and spliced only
    # when the route says it answered with a slice.
    assert "S.chat.turns.some(t => t.id === sinceTurnId)" in block
    assert 'heldTurns ? "?since_turn_id=" + sinceTurnId : ""' in block
    assert "if (heldTurns && chat.turns_since != null)" in block
    # And passed only by a run that APPENDS a turn: every rewrite of an
    # existing one names it in `run.turnId`.
    assert "const heldTurnId = (!run.turnId" in stream
    assert "{ sinceTurnId: heldTurnId }" in stream


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
        ('$("#b-style").onclick', '$("#b-dlg").onclick', "style_guide"),
        ('$("#b-dlg").onclick', "// The Cast modal", "dialogue_config"),
    ]
    for start, end, endpoint in cases:
        block = _between(SETTINGS, start, end)
        assert "const chatId = S.chatId;" in block
        assert "if (S.chatId !== chatId) return;" in block
        assert f"/api/chats/${{chatId}}/{endpoint}" in block
        assert "/api/chats/${S.chatId}" not in block

    # The world and attire dialogs moved to world_browser.js (2026-09-04),
    # where one dialog reads the room index, the slices and the raw editors'
    # own endpoints, every request against the chat captured at open.
    block = _between(WORLD_BROWSER, "async function openWorldBrowser(",
                     '$("#b-world").onclick')
    assert "const chatId = S.chatId;" in block
    assert "if (S.chatId !== chatId) return;" in block
    assert "/api/chats/${chatId}/rooms" in block
    for endpoint in ("world", "attire", "rooms", "positions"):
        assert f"/api/chats/${{chatId}}/{endpoint}" in WORLD_BROWSER, endpoint
    assert "/api/chats/${S.chatId}" not in WORLD_BROWSER


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
    block = _between(CHAT, "function observeVisibleTurn(", "async function openChat(id")

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
        SETTINGS + WORLD_BROWSER))
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


def test_the_pipeline_drawer_explains_a_turn_blocked_by_another_frame():
    """`blocked_by_other_frame` is computed separately from `editable` "so the
    UI can explain WHY a frame-latest turn is still blocked, instead of just
    refusing". Nothing read it: the drawer opened with Resume, reroll, use and
    edit absent and no reason given.

    The sentence is the route's own 409 detail, so the reader gets the same
    wording whether the drawer explains it up front or the route refuses the
    attempt. Two copies of one message drift, so they are pinned equal here.
    """
    assert "p.blocked_by_other_frame" in CHAT

    server = (ROOT / "web/app.py").read_text(encoding="utf-8")
    sentence = ("Another frame has advanced since this turn. Recompute here "
                "would silently roll back that frame's progress too -- shared "
                "state (memories, cast, world entities) isn't sliced per frame "
                "in this version.")
    # Present in both, modulo each language's own string-concatenation breaks.
    assert sentence in re.sub(r'"\s*\n\s*"', "", server)
    assert sentence in re.sub(r'"\s*\n\s*\+ "', "", CHAT)


def test_a_failed_quick_start_removes_the_rows_it_generated():
    """The wizard generates the persona and cast BEFORE the chat exists and,
    until 2026-09-03, deleted only the chat on failure: measured on the
    owner's database, five generated "Vespera" rows and a generated "The
    Doctor" attached to no chat, one per retried quick start (the greeting
    path generates nothing, so it never showed it). The run records every
    library row it generated and the cleanup removes them with the chat;
    rows the player chose from the library are never touched."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "static" / "js" / "app.js"
           ).read_text("utf-8")
    run = src[src.index("async function runWizard("):src.index("function renderCharacterSidebar(")]
    assert "created.personas.push(r.id)" in run
    assert "created.characters.push(r.id)" in run
    assert "discardFailedStorySetup(chat, created)" in run
    cleanup = src[src.index("async function discardFailedStorySetup("):src.index("function wizardFromScratch(")]
    assert "created.characters" in cleanup and "`/api/characters/${id}`" in cleanup
    assert "created.personas" in cleanup and "`/api/personas/${id}`" in cleanup
    assert "existingCharacterIds" not in cleanup, "library picks are never deleted"


def test_every_run_scoped_write_names_the_story_and_frame_it_belongs_to():
    """A73 (review 2026-09-07). The story list is not busy-gated, so a reader
    can open another story -- or another frame of the same one -- while a beat
    is still running, and two long-lived pieces of state outlive that switch:
    `_activeRun`, until the stream ends, and the reroll arrows, which keep
    whatever turn they were mounted on.

    Measured then: the arrow keys POSTed a narration select against the other
    story's turn, and the early-narration preview appended story A's prose into
    story B's transcript. Both are writes made from state read before the
    switch, so the check has to sit at the write.

    A browser tier would drive it: start a beat in A, click B in the sidebar
    before the narrator step lands, and assert B's transcript never grows and
    that ArrowLeft posts nothing.
    """
    scope = _between(CHAT, "function inCurrentScope(scope)", "const _NARRATION_STEPS")
    assert "scope.chatId === S.chatId" in scope
    assert "(scope.frameId ?? null) === (S.currentFrameId ?? null)" in scope

    preview = _between(CHAT, "function showNarrationEarly(ev)",
                       "function clearNarrationEarly()")
    assert "if (!inCurrentScope(_activeRun)) return;" in preview

    # The arrows carry the scope they were mounted in, and re-check it before
    # painting or posting.
    mount = _between(CHAT, "async function _mountRerollNav(", "function _paintRerollCount()")
    assert "const scope = { chatId: S.chatId, frameId: S.currentFrameId };" in mount
    assert "if (!turnEl.isConnected || !inCurrentScope(scope)) return;" in mount
    assert "RR.chatId = scope.chatId;" in mount
    assert "RR.frameId = scope.frameId;" in mount

    flip = _between(CHAT, "async function showRerollVariant(next)",
                    "// \u2190 and \u2192 anywhere")
    assert "if (!inCurrentScope(RR)) return false;" in flip
    assert flip.index("if (!inCurrentScope(RR)) return false;") < flip.index("api(\"POST\"")

    # A render with no newest turn to mount on is what left them live: an empty
    # story, or a frame with no turns.
    render = _between(CHAT, "function renderChat()", "function branchTurn(")
    assert "resetRerollNav();" in render

    # And the just-generated marker belongs to the run's own story.
    stream = _between(CHAT, "async function runStream(", "// Rerolling/resuming/")
    assert "if (ok && S.chatId === run.chatId) _freshRunPending = true;" in stream


def test_the_writers_room_answer_belongs_to_the_story_it_was_asked_in():
    """A73, the other half of the class. The Writers' Room panel is the second
    place a stream outlives the page it was started from, and it had no scope
    check at all: `roomStream` awaits a stream opened against `S.chatId`, and
    `roomEvent` writes ROOM.messages/mandates/status/citations whenever a frame
    arrives.

    `room_done` is the branch that made it stick rather than merely show: it
    appends the old story's replies AND stamps `ROOM.loadedKey = roomKey()`
    with the NEW story's key -- the exact equality `roomStartWatch` polls to
    notice it is showing the wrong thread -- so the self-heal was disarmed by
    the same write that needed it.

    A browser tier would drive it: ask the room a question in story A, switch
    to B before the answer lands, and assert B's panel never gains A's replies
    and that the watch reloads B's own thread.
    """
    scope = _between(WRITERS_ROOM, "function roomScope()", "function roomFrameQuery()")
    assert "chatId: S.chatId" in scope
    assert "frameId: S.currentFrameId ?? null" in scope

    stream = _between(WRITERS_ROOM, "async function roomStream(text)",
                      "function roomEvent(")
    assert "const scope = roomScope();" in stream
    assert "(event) => roomEvent(event, scope)" in stream

    event = _between(WRITERS_ROOM, "function roomEvent(event, scope)",
                     "async function roomRevoke(")
    assert "if (!inCurrentScope(scope)) return;" in event
    assert event.index("if (!inCurrentScope(scope)) return;") < event.index(
        "ROOM.loadedKey = roomKey();")

    # The two other awaits that write ROOM state get the same rule -- an
    # earlier page prepended into another story's thread, and a revoke's
    # mandate list landing on the wrong story, are the same mistake.
    for fn, end in (("async function roomLoadEarlier()", "function roomStartWatch()"),
                    ("async function roomRevoke(uid)", "// ---- Rendering")):
        block = _between(WRITERS_ROOM, fn, end)
        assert "const scope = roomScope();" in block, fn
        assert "if (!inCurrentScope(scope)) return;" in block, fn

    # `inCurrentScope` is chat.js's, and chat.js is loaded before this file --
    # one statement of the rule, not two.
    assert "function inCurrentScope(" not in WRITERS_ROOM
    index = (ROOT / "static/index.html").read_text(encoding="utf-8")
    assert index.index("js/chat.js") < index.index("js/writers_room.js")


def test_the_raw_record_editor_saves_only_what_it_just_read():
    """A18 (review 2026-09-07). The world PUT is `DELETE FROM world WHERE
    chat_id=?` followed by a rewrite from the request body, so this textarea is
    the whole record and an old copy of it does not merge -- it deletes what the
    story wrote since.

    The tab used to render from a copy held for the dialog's lifetime, with two
    `delete state.cache.raw` calls elsewhere standing between that copy and a
    silent revert. It is read fresh on every entry now, and the reader's own
    window -- a beat committing while the editor sits open, which
    `_require_chat_idle` on the route does not cover because the story is idle
    again by then -- is closed by re-reading at the moment of saving.

    A browser tier would drive it: open the Raw JSON tab, commit a beat in
    another window, press Save, and assert the confirm appears and that
    declining leaves the beat's world intact.
    """
    block = _between(WORLD_BROWSER, "function wbRenderRaw(", "// ---- The map editor")
    assert "cache" not in block.split("const render = data => {")[0]
    assert "const base = JSON.stringify(data);" in block
    assert 'current = await api("GET", path);' in block
    assert "JSON.stringify(current) !== base" in block
    assert "await confirmModal(" in block
    assert block.index("JSON.stringify(current) !== base") < block.index('api("PUT", path, j)')
    # And the sentence says what THIS tab's PUT costs. `world_put` deletes the
    # row and rewrites it; `attire_put` writes the bodies it is named and
    # leaves the rest of the ledger, so one wording for both overstated the
    # loss on the attire tab (A18 sibling).
    confirm = block[block.index("await confirmModal("):
                    block.index("confirmLabel: \"Save anyway\"")]
    assert "isAttire" in confirm
    # Whole sentences, one per branch: `t()` looks a message up by the string
    # the browser hands it, so a sentence assembled from a shared opening and a
    # differing clause is one no catalog can hold.
    joined = re.sub(r'"\s*\n\s*\+ "', "", confirm)
    assert "Saving replaces everything it wrote. Save anyway?" in joined
    assert ("Saving overwrites every body this copy names; a body it does not "
            "name keeps what the story wrote. Save anyway?") in joined
    for sentence in ("The story has written to this record since it was "
                     "opened -- a beat committed, or another window saved. "
                     "Saving replaces everything it wrote. Save anyway?",
                     "The story has written to this ledger since it was "
                     "opened -- a beat committed, or another window saved. "
                     "Saving overwrites every body this copy names; a body it "
                     "does not name keeps what the story wrote. Save anyway?"):
        assert sentence in CATALOG, sentence
    # No copy of the record survives the render, so nothing has to remember to
    # invalidate one.
    assert "delete state.cache.raw" not in WORLD_BROWSER
    assert "cache: {}," not in WORLD_BROWSER
