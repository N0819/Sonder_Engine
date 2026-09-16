"""Read-only display projections of saved pipeline output."""

import json

from agents.composer import perception_packet


def saved_perception_packets(content):
    """Group each saved observer's admitted view without rewriting the variant.

    This is the same presentation seam used by cognition, applied to the
    selected stage's evidence. No current scene or identity lookup belongs in
    an archive display. A view-only archive keeps its prose as context.
    """
    try:
        output = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(output, dict):
        return None
    views = output.get("views")
    if not isinstance(views, dict) or not views:
        return None
    observations = output.get("observations")
    if not isinstance(observations, dict):
        observations = {}
    packets = {}
    for observer, view in views.items():
        rows = observations.get(observer)
        if not isinstance(rows, list):
            rows = []
        # Manually edited variants may contain malformed rows. Their admitted
        # prose still survives through fallback_view, without guessing a phase.
        rows = [row for row in rows if isinstance(row, dict)
                and (row.get("phase") is None or isinstance(row["phase"], str))
                and isinstance(row.get("observed"), dict)
                and isinstance(row["observed"].get("text"), str)]
        # None means "no filter" to the shared helper. A saved null view means
        # nothing was delivered, so it must instead be passed as empty text.
        packets[observer] = perception_packet(
            rows, fallback_view=view if isinstance(view, str) else "")
    return packets
