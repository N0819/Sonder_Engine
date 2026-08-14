"""Static checks for the two reader-facing signals added around a finished turn.

The frontend has no bundler and no browser-test dependency, so these follow the
convention of `test_frontend_state_guards.py`: pin the small decisions whose
whole value is that they are easy to undo by accident.

Both features exist because a turn in this engine is a long wait. The chime is
how you learn it ended from another tab; the version arrows are how you compare
what came back against what came back last time.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "static/js/chat.js").read_text(encoding="utf-8")
CHIME = (ROOT / "static/js/chime.js").read_text(encoding="utf-8")
INDEX = (ROOT / "static/index.html").read_text(encoding="utf-8")


class TestTheChimeStaysAudibleFromAnotherTab:

    def test_it_is_loaded_before_the_file_that_calls_it(self):
        assert INDEX.index("chime.js") < INDEX.index("chat.js")

    def test_the_envelope_is_scheduled_on_the_audio_clock(self):
        """A backgrounded tab has its timers throttled to roughly once a
        second, which would smear the two notes into something arrhythmic.
        `ctx.currentTime` runs at audio rate whatever the page is doing."""
        assert "ctx.currentTime" in CHIME
        # The CALL, not the word -- the header explains at length why neither
        # timer is used, and that prose is the point of the file.
        assert "setTimeout(" not in CHIME
        assert "setInterval(" not in CHIME

    def test_the_context_is_unlocked_on_the_gesture_that_starts_the_wait(self):
        """Browsers refuse audio until the user has interacted, and by the time
        the turn lands the reader is in another tab with no gesture left to
        spend. Send is the gesture."""
        assert "if (typeof chimeArm === \"function\") chimeArm();" in CHAT
        assert CHAT.index("chimeArm()") < CHAT.index("chimePlay()")

    def test_it_sounds_only_on_a_run_that_succeeded(self):
        """A failure already raises a toast, and a chime meaning "ready" must
        not also mean "gone wrong"."""
        assert "if (ok && typeof chimePlay === \"function\") chimePlay();" in CHAT

    def test_mute_is_sticky_without_a_round_trip(self):
        assert 'localStorage.getItem("chime.muted")' in CHIME
        assert 'localStorage.setItem("chime.muted"' in CHIME

    def test_it_stays_quiet(self):
        """Noticeable from the next tab and ignorable from this one is a much
        softer target than an alert, and the peak gain is the whole of it."""
        assert "level: 0.06" in CHIME


class TestTheChimeCoversEveryLongGeneration:
    """A turn is not the only thing that takes minutes -- generating a
    character, filling a psychology sheet, drafting a persona, building a
    lorebook are all start-it-and-go-elsewhere operations, and all of them are
    ordinary `api()` calls rather than the pipeline stream."""

    def test_the_rule_is_duration_not_a_list_of_routes(self):
        """A named list would be wrong the first time somebody adds a route."""
        assert "CHIME_MIN_MS = 4000" in CHIME
        assert "elapsedMs >= CHIME_MIN_MS" in CHIME

    def test_backdrops_and_ambience_are_excluded(self):
        """The picture appears and the sound starts; both announce themselves,
        and ringing a bell to announce a sound is the definition of
        obnoxious."""
        source = "const CHIME_EXCLUDED = "
        line = CHIME[CHIME.index(source):].split("\n", 1)[0]

        assert "backdrops?" in line
        assert "ambience" in line

    def test_reads_never_chime(self):
        assert "CHIME_MUTATIONS = /^(POST|PUT|PATCH)$/i" in CHIME

    def test_api_arms_on_the_way_in_and_sounds_on_the_way_out(self):
        utils = (ROOT / "static/js/utils.js").read_text(encoding="utf-8")
        body = utils[utils.index("async function api(method, url, body)"):]
        body = body[:body.index("async function streamPost")]

        assert body.index("chimeArm()") < body.index("chimeWorkFinished(")
        assert "performance.now()" in body
        # Past every throw above it, so only a success can reach it.
        assert body.index("throw new Error(message") < body.index(
            "chimeWorkFinished(")

    def test_the_turn_stream_does_not_double_up_with_the_api_hook(self):
        """`runStream` goes through `streamPost`, which has no hook, so a
        finished turn chimes once from chat.js and never twice."""
        utils = (ROOT / "static/js/utils.js").read_text(encoding="utf-8")
        stream = utils[utils.index("async function streamPost"):]

        assert "chimeWorkFinished" not in stream
        assert "chimePlay" not in stream


class TestBrowsingTheRerollsOfTheNewestBeat:

    def test_the_arrows_are_mounted_only_on_the_last_turn(self):
        block = CHAT[CHAT.index("if (isLast) {"):]
        assert "_mountRerollNav(t.id, d);" in block[:600]

    def test_the_flip_paints_before_it_persists(self):
        """The prose is already in hand, so a round trip per arrow press would
        make comparing two versions feel like loading.

        Pinned on `paintProse` rather than a raw `.textContent` write: the
        variant is painted through the speaker-colouring path now, so the flip
        keeps each character's dialogue tinted instead of dropping to flat
        text until the next full chat load."""
        body = CHAT[CHAT.index("async function showRerollVariant"):]
        body = body[:body.index("document.addEventListener")]
        assert body.index("paintProse(RR.proseEl") < body.index(
            'api("POST"')

    def test_arrow_keys_yield_to_anything_with_a_caret(self):
        body = CHAT[CHAT.index('if (event.key !== "ArrowLeft"'):]
        body = body[:body.index("showRerollVariant(RR.index +")]

        assert "active.isContentEditable" in body
        assert "/^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName)" in body
        assert "$(\"#modal\").classList.contains(\"hidden\")" in body

    def test_arrow_keys_are_not_claimed_when_there_is_nothing_to_flip(self):
        """Ordinary horizontal scrolling still works on a story with no
        rerolls, so preventDefault comes after the count check."""
        body = CHAT[CHAT.index('if (event.key !== "ArrowLeft"'):]
        body = body[:body.index("showRerollVariant(RR.index +")]

        assert body.index("if (RR.variants.length < 2) return;") < body.index(
            "event.preventDefault();")

    def test_it_refuses_to_flip_mid_generation(self):
        body = CHAT[CHAT.index("async function showRerollVariant"):]
        assert "if (S.busy || RR.variants.length < 2) return false;" in body

    def test_the_mount_drops_a_response_the_transcript_outran(self):
        """A reroll finishing or a different story opening rebuilds the
        transcript, and the nav's own fetch can land after that."""
        body = CHAT[CHAT.index("async function _mountRerollNav"):]
        body = body[:body.index("function _paintRerollCount")]

        assert "if (!turnEl.isConnected) return;" in body
        assert "if (variants.length < 2) return;" in body


class TestTheNarrationPreviewLooksLikeAFinishedTurn:
    """Reported live: two boxes with the same prose, the extra one uncoloured,
    vanishing when commit finished and leaving the correct turn behind.

    The preview is wanted -- it spares a reader the whole commit tail for
    words that already exist. Two things were wrong with it. It appended a
    bare slab of prose even when the turn it was previewing was ALREADY on
    screen, which is the common path (rerolling narration is what someone
    does while tuning it). And it built that prose the raw way while every
    other render went through the speaker-colouring path, so the copy was
    flat.

    Now: a re-run repaints the turn where it sits, and a turn nobody has seen
    yet gets the player's own line above the prose, so the preview reads as
    the finished beat rather than as a stray message.
    """

    def test_a_rendered_turn_can_be_found_by_id(self):
        """Without this the preview cannot reach the element it should be
        repainting, and appending is the only option left."""
        assert '"data-turn": t.id,' in CHAT

    def test_a_re_run_repaints_in_place_and_appends_nothing(self):
        body = CHAT[CHAT.index("function showNarrationEarly"):]
        body = body[:body.index("\n}\n")]
        repaint = body[:body.index("let d = document.getElementById")]
        assert '.turn[data-turn="${turnId}"] .prose' in repaint
        assert "paintProse(live" in repaint
        # Returns before it can reach the append path below.
        assert "return;" in repaint

    def test_a_new_turn_previews_the_players_line_with_it(self):
        body = CHAT[CHAT.index("function showNarrationEarly"):]
        body = body[:body.index("\n}\n")]
        assert '_activeRun.playerInput' in body
        assert 'el("div", { class: "pin" }, said)' in body

    def test_the_preview_goes_through_the_colouring_path(self):
        body = CHAT[CHAT.index("function showNarrationEarly"):]
        body = body[:body.index("\n}\n")]
        assert "paintProse(" in body
        assert 'el("div", { class: "prose" }, prose)' not in body

    def test_every_re_run_caller_says_which_turn_it_is_re_running(self):
        """reroll, rerun-from-step, step reroll and resume all know the id; a
        caller that forgets it silently falls back to appending a duplicate
        rather than failing, which is why this is pinned."""
        assert CHAT.count("{ turnId: tid }") == 4
        assert "turnId: context.turnId !== undefined" in CHAT
