"""Reference extension for the narration seam and the module UI surface.

`cohesion-demo` shows the pipeline half: a stage, per-story state, a route, a
sidebar panel. This one shows the half that reaches the READER — a standing
block of narration context installed per story, edited from a full-window view
that is an ES module rather than a single script.

Together they are the two directions an extension can act in. Nothing here is
clever; the point is that every call it makes is one an author can copy.
"""

MAX_FRAME = 600


def register(api):
    """Two routes: read the story's standing frame, and set it."""

    def read_frame(request):
        chat_id = request.chat_id
        if chat_id is None:
            return {"frame": None, "chat_id": None}
        block = api.narration_context(chat_id).get() or {}
        return {
            "chat_id": chat_id,
            "frame": block.get("text") or "",
            "revision": block.get("revision") or 0,
        }

    def write_frame(request):
        chat_id = request.chat_id
        if chat_id is None:
            raise api_error("a story has to be open to set its frame")
        text = str((request.body or {}).get("frame") or "").strip()
        # Bounded well under the host's own ceiling. The host refuses an
        # oversized block rather than truncating it, and a demo that let a
        # reader hit that refusal by typing would be teaching the wrong lesson.
        if len(text) > MAX_FRAME:
            raise api_error(f"keep the frame under {MAX_FRAME} characters")
        block = api.narration_context(chat_id)
        # `set("")` clears, so the empty case needs no branch of its own --
        # but say so, because "saving nothing removes it" is a real behaviour
        # a reader will rely on.
        stored = block.set(text)
        return {
            "chat_id": chat_id,
            "frame": (stored or {}).get("text") or "",
            "revision": (stored or {}).get("revision") or 0,
        }

    api.add_route("/frame", read_frame, methods=("GET",))
    api.add_route("/frame", write_frame, methods=("POST",))


def api_error(message):
    """A 400 rather than a 500, which is what a bad request deserves."""
    from extension_runtime import ExtensionError

    return ExtensionError(message)
