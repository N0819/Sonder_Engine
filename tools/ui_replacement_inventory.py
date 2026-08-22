"""Generate deterministic evidence inventories for the UI replacement.

This is deliberately a source census, not a JavaScript correctness checker.
It records current integration surfaces so a later package cannot remove one
without producing an inspectable inventory diff.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


ROUTE = re.compile(
    r"^\s*@(?:app|router)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
WINDOW_GLOBAL = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)\s*=")
CLASSIC_DECLARATION = re.compile(
    r"^(?:(const|let|var)\s+([A-Za-z_$][\w$]*)|function\s+([A-Za-z_$][\w$]*)\s*\()"
)
MODULE_DECLARATION = re.compile(r"(?m)^\s*(?:import|export)\b")
DOM_REFERENCE = re.compile(
    r"(?:getElementById\(\s*[\"']([^\"']+)[\"']|"
    r"querySelector(?:All)?\(\s*[\"']#([A-Za-z_][\w:.-]*))"
)
THEME = re.compile(r"data-theme\s*=\s*[\"']([^\"']+)[\"']")
CUSTOM_PROPERTY = re.compile(r"(?<![\w-])(--[A-Za-z0-9_-]+)\s*:")

DRIFT_PATHS = (
    "static",
    "web",
    "language_packs",
    "extension_runtime",
    "extensions",
    "browser_tests",
    "tests",
    "tools",
)
CANDIDATE_DIRECT_COLLISIONS = frozenset({
    "language_packs/en/ui.json",
    "language_packs/ja/ui.json",
})


CAPABILITIES = (
    ("CAP-PLAY-OPEN", "Open and switch stories", "static/js/ui-next/play-runtime.js; /api/chats/{cid}", "WP-04", "required", "replace"),
    ("CAP-PLAY-TRANSCRIPT", "Read transcript and player turns", "static/js/ui-next/play-view.js", "WP-04", "required", "adapt"),
    ("CAP-PLAY-STREAM", "Submit, stream, stop, retry, and recover turns", "static/js/ui-next/play-runtime.js; pipeline routes", "WP-04", "required", "adapt"),
    ("CAP-PLAY-DRAFT", "Keep composer drafts isolated per story", "composer input and browser state", "WP-04", "required", "rebuild"),
    ("CAP-PLAY-SCROLLBACK", "Load long transcript scrollback", "static/js/ui-next/play-runtime.js; Play browser tests", "WP-04", "required", "adapt"),
    ("CAP-PLAY-REROLL", "Reroll and select narration variants", "static/js/ui-next/play-runtime.js; narration variant routes", "WP-04", "required", "adapt"),
    ("CAP-PLAY-FRAMES", "Inspect and select story frames", "frame routes and current dialogs", "WP-05", "required", "adapt"),
    ("CAP-PLAY-CONDITION", "View player and NPC condition/vitals", "static/js/ui-next/story-tools/conditions.js; vitals routes; UNBUILT §1.66", "WP-05", "required", "rebuild"),
    ("CAP-PLAY-WORLD", "Inspect world and positions", "world/position routes and dialogs", "WP-05", "required", "replace"),
    ("CAP-PLAY-CAST", "Manage current story cast", "character association routes and dialogs", "WP-05", "required", "replace"),
    ("CAP-PLAY-STYLE", "Edit style guide and dialogue configuration", "style/dialogue routes", "WP-05", "required", "replace"),
    ("CAP-PLAY-ATTIRE", "Inspect and author attire", "attire route and authoring dialog", "WP-05", "required", "replace"),
    ("CAP-PLAY-BACKDROP", "Commission, select, and display backdrops", "static/js/ui-next/story-tools/backdrops.js", "WP-05", "required", "adapt"),
    ("CAP-PLAY-AMBIENCE", "Search, pin, play, mute, and stop ambience", "static/js/ui-next/story-tools/ambience.js", "WP-05", "required", "adapt"),
    ("CAP-PLAY-WEATHER", "Render and configure weather effects", "static/js/ui-next/play-view.js; UNBUILT §2.11", "WP-05", "required", "adapt"),
    ("CAP-LIB-STORIES", "List, search, create, rename, archive, import, and export stories", "static/js/ui-next/library-runtime.js; chat routes", "WP-06", "required", "rebuild"),
    ("CAP-LIB-CHARACTERS", "List, import, export, edit, and reuse characters", "static/js/ui-next/library-authoring-runtime.js", "WP-06", "required", "rebuild"),
    ("CAP-LIB-PERSONAS", "List, import, export, edit, and reuse personas", "static/js/ui-next/library-authoring-runtime.js", "WP-06", "required", "rebuild"),
    ("CAP-LIB-LORE", "Browse, edit, import, export, and reuse lorebooks", "static/js/ui-next/library-runtime.js", "WP-06", "required", "rebuild"),
    ("CAP-LIB-SCOPE", "Filter reusable assets by story association", "association routes", "WP-06", "required", "rebuild"),
    ("CAP-LIB-EDITORS", "Preserve every editor field, validation, and draft", "static/js/ui-next/library-authoring-runtime.js; library-editors/", "WP-07", "required", "replace"),
    ("CAP-SET-EXPERIENCE", "Configure theme, reading, language, sound, motion, and accessibility", "static/js/ui-next/settings-view.js; static/css/ui/themes/", "WP-08", "required", "replace"),
    ("CAP-SET-AI", "Configure providers, models, roles, credentials, and generation defaults", "static/js/ui-next/settings-view.js; provider routes", "WP-08", "required", "replace"),
    ("CAP-SET-CONTENT", "Configure content/data handling and imports/exports", "static/js/ui-next/settings-view.js", "WP-08", "required", "replace"),
    ("CAP-SET-ADDONS", "Install, configure, enable, disable, update, and retire extensions", "static/js/ui-next/extensions.js; extension routes", "WP-08", "required", "replace"),
    ("CAP-SET-MAINT", "Run updates, backups, repairs, logs, and maintenance", "static/js/ui-next/settings-view.js; maintenance routes; UNBUILT §1.58", "WP-08", "required", "replace"),
    ("CAP-SET-ADVANCED", "Edit prompts, parameters, diagnostics, and raw story data", "static/js/ui-next/settings-view.js", "WP-08", "required", "replace"),
    ("CAP-NEW-DESCRIBE", "Create a generated story from a description", "newChatWizard and chat creation routes", "WP-09", "required", "adapt"),
    ("CAP-NEW-LIBRARY", "Create a story from reusable Library assets", "current creation and association routes", "WP-09", "required", "replace"),
    ("CAP-NEW-BLANK", "Create a blank story without a provider", "chat creation route", "WP-09", "required", "adapt"),
    ("CAP-AUTH-SETUP", "Claim a new host safely", "static/login.html; auth setup route", "WP-10", "required", "adapt"),
    ("CAP-AUTH-LOGIN", "Sign in, lock out abusive retries, and sign out", "login.html; auth routes", "WP-10", "required", "adapt"),
    ("CAP-AUTH-SESSION", "Recover predictably from session expiry", "API/session guards", "WP-10", "required", "adapt"),
    ("CAP-GUEST-JOIN", "Redeem a guest join code", "static/guest.html; guest routes", "WP-11", "required", "adapt"),
    ("CAP-GUEST-PLAY", "Read and submit guest turns with session limits", "guest.html; guest state/turn routes", "WP-11", "required", "adapt"),
    ("CAP-THEME-CURATED", "Use curated semantic themes without layout changes", "static/css/ui/themes/; static/js/ui/appearance.js", "WP-12", "required", "replace"),
    ("CAP-THEME-LEGACY", "Retain usable Legacy theme mappings", "static/js/ui-next/settings-view.js", "WP-12", "required", "adapt"),
    ("CAP-A11Y", "Use keyboard, screen reader, zoom, contrast, motion, and target preferences", "HTML/CSS/browser behavior", "WP-01", "required", "replace"),
    ("CAP-I18N", "Render UI copy through language packs without translating user data", "static/js/i18n.js; language_packs; UNBUILT §1.48", "WP-02", "required", "replace"),
    ("CAP-EXT-V1", "Run supported extension v1 UI and lifecycle", "static/js/ui-next/extensions-v1.js; /api/extensions", "WP-12", "required", "preserve"),
    ("CAP-EXT-V2", "Register versioned routes, slots, tasks, permissions, and teardown", "static/js/ui-next/extensions.js; static/js/ui-next/extension-host.js; browser_tests/test_ui_wp12.py", "WP-12", "required", "rebuild"),
    ("CAP-LIVING-WORLD", "Configure built living-world floors without overstating ceilings", "static/js/ui-next/settings-view.js; LIVING_WORLD_BUILT; UNBUILT §6.8", "WP-08", "required", "replace"),
    ("CAP-ENGINE-NOTES", "Inspect per-turn engine notes and warnings", "pipeline drawer; UNBUILT §1.11", "WP-04", "required", "adapt"),
    ("CAP-TASKS", "Show persistent async tasks, progress, cancellation, and recovery", "static/js/ui-next/tasks.js and route-specific surfaces", "WP-02", "required", "rebuild"),
    ("CAP-NOTICES", "Show contextual errors and persistent extension notices", "static/js/ui-next/notices.js; static/js/ui-next/extensions.js", "WP-02", "required", "rebuild"),
    ("CAP-ARCHIVE", "Archive, restore, branch, and checkpoint without semantic drift", "server routes and persistence", "WP-07", "required", "preserve"),
    ("CAP-IMPORT-EXPORT", "Round-trip all supported authored records", "route-specific import/export", "WP-07", "required", "preserve"),
    ("CAP-DEFAULT-CUTOVER", "Replace the root entry and delete classic host code", "static/ui-next.html and web/app.py root route", "WP-13", "required", "remove-at-cutover"),
    ("CAP-RESPONSIVE", "Keep all capabilities through desktop, tablet, phone, landscape, and zoom", "static/css/ui/; browser tests", "WP-14", "required", "rebuild"),
)

UNBUILT_UI_OWNERSHIP = (
    ("1.11", "Aggregate/live engine-warning visibility", "WP-04", "Preserve per-turn notes; replacement may add an aggregate reader but does not change warning production."),
    ("1.48", "Language-pack unfinished work and UI catalog boundary", "WP-02, WP-14", "All replacement copy uses catalogs; Japanese quality and story-language persistence remain their existing engine/product debts."),
    ("1.58", "Four dead settings keys awaiting live-data migration decision", "WP-08", "Do not expose dead controls or delete stored values; replacement follows the eventual server decision."),
    ("1.60", "Editable generalization tags overpromise runtime behavior", "WP-07", "Preserve authored values and label truthfully; UI replacement does not invent the missing psychology mechanism."),
    ("1.66", "Story-column floor can defeat vitals/utility reservation", "WP-05", "Story content, conditions, utilities, and composer never overlap continuously across supported width and zoom states."),
    ("2.8", "Off-screen life presentation must match built authority", "WP-08", "Read the server ladder and LIVING_WORLD_BUILT; never mark an unbuilt ceiling as operational."),
    ("2.10", "Session digest is not built", "WP-04", "No replacement control implies a digest exists; add presentation only if an authoritative backend lands separately."),
    ("2.11", "Weather rendering has bounded visual gaps", "WP-05", "Preserve current rain/snow/lightning behavior and state the limits; do not enlarge engine scope inside UI work."),
    ("6.2", "Extension residuals include untranslated errors and incomplete teardown", "WP-12", "Own UI catalog reach, v1 adapter, v2 lifecycle, permissions, containment, and teardown; unrelated storage/model-lane debt stays separate."),
    ("6.8", "Living-world settings can overstate requested ceilings", "WP-08", "Render built floors and effective depth from server authority, including unavailable/partial explanations."),
    ("6.10", "Extra-body-part editor menus carry deliberately open mechanics", "WP-07", "Preserve all current fields and menus without presenting residual simulation mechanics as built."),
)


class _EntryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.scripts: set[str] = set()
        self.styles: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "script" and values.get("src"):
            self.scripts.add(str(values["src"]))
        if tag == "link" and "stylesheet" in str(values.get("rel") or "").split():
            if values.get("href"):
                self.styles.add(str(values["href"]))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _flatten_keys(value: object, prefix: str = "") -> Iterable[str]:
    if isinstance(value, dict):
        for key in sorted(value):
            name = f"{prefix}.{key}" if prefix else str(key)
            child = value[key]
            if isinstance(child, dict):
                yield from _flatten_keys(child, name)
            else:
                yield name


def collect_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    routes: list[dict[str, str]] = []
    entries: list[dict[str, object]] = []
    globals_: list[dict[str, str]] = []
    dom_references: list[dict[str, str]] = []
    themes: set[str] = set()
    custom_properties: set[str] = set()
    catalog_keys: set[str] = set()

    for path in sorted((root / "web").rglob("*.py")) if (root / "web").exists() else []:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if match := ROUTE.match(line):
                routes.append({
                    "method": match.group(1).upper(),
                    "path": match.group(2),
                    "source": f"{_relative(path, root)}:{number}",
                })

    for path in sorted((root / "static").glob("*.html")) if (root / "static").exists() else []:
        parser = _EntryParser()
        parser.feed(path.read_text(encoding="utf-8"))
        entries.append({
            "dom_ids": sorted(parser.ids),
            "path": _relative(path, root),
            "scripts": sorted(parser.scripts),
            "styles": sorted(parser.styles),
        })

    for path in sorted((root / "static" / "js").rglob("*.js")) if (root / "static" / "js").exists() else []:
        text = path.read_text(encoding="utf-8")
        is_module = bool(MODULE_DECLARATION.search(text))
        for number, line in enumerate(text.splitlines(), 1):
            source = f"{_relative(path, root)}:{number}"
            if not is_module and (match := CLASSIC_DECLARATION.match(line)):
                if match.group(3):
                    globals_.append({"kind": "classic-function", "name": match.group(3), "source": source})
                else:
                    globals_.append({"kind": f"classic-{match.group(1)}", "name": match.group(2), "source": source})
            for match in WINDOW_GLOBAL.finditer(line):
                globals_.append({"kind": "window", "name": match.group(1), "source": source})
            for match in DOM_REFERENCE.finditer(line):
                dom_references.append({"id": match.group(1) or match.group(2), "source": source})

    for path in sorted((root / "static").rglob("*.css")) if (root / "static").exists() else []:
        text = path.read_text(encoding="utf-8")
        themes.update(THEME.findall(text))
        custom_properties.update(CUSTOM_PROPERTY.findall(text))

    for path in sorted((root / "language_packs").rglob("ui.json")) if (root / "language_packs").exists() else []:
        catalog_keys.update(_flatten_keys(json.loads(path.read_text(encoding="utf-8"))))

    routes.sort(key=lambda row: (row["path"], row["method"], row["source"]))
    globals_.sort(key=lambda row: (row["source"], row["kind"], row["name"]))
    dom_references.sort(key=lambda row: (row["source"], row["id"]))
    return {
        "browser_globals": globals_,
        "css_custom_properties": sorted(custom_properties),
        "dom_references": dom_references,
        "entries": entries,
        "extension_routes": [row for row in routes if row["path"].startswith("/api/extensions")],
        "routes": routes,
        "themes": sorted(themes),
        "ui_catalog_keys": sorted(catalog_keys),
    }


def classify_drift_path(path: str) -> str:
    """Return the review boundary a changed frontend-adjacent path belongs to."""

    path = path.replace("\\", "/")
    if path.startswith("language_packs/") and path.endswith("/ui.json"):
        return "localization-contract"
    if path.startswith("extension_runtime/") or path.startswith("extensions/"):
        return "extension-contract"
    if path.startswith("web/auth") or path.startswith("web/guest"):
        return "security-contract"
    if path.startswith("web/"):
        return "api-contract"
    if path.startswith("static/js/"):
        return "frontend-behavior"
    if path.startswith("static/"):
        return "presentation"
    if path.startswith("browser_tests/") or path.startswith("tests/test_frontend") or path.startswith("tests/test_ui"):
        return "behavioral-test"
    if path.startswith("tools/"):
        return "tooling"
    return "engine-or-test-context"


def collect_drift(root: Path, from_ref: str, to_ref: str) -> list[dict[str, str]]:
    command = [
        "git", "-C", str(root), "diff", "--name-status",
        f"{from_ref}..{to_ref}", "--", *DRIFT_PATHS,
    ]
    output = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1].replace("\\", "/")
        rows.append({
            "status": status,
            "path": path,
            "classification": classify_drift_path(path),
            "candidate_collision": "yes" if path in CANDIDATE_DIRECT_COLLISIONS else "no",
        })
    return sorted(rows, key=lambda row: row["path"])


def write_drift_artifact(output: Path, root: Path, from_ref: str, to_ref: str) -> None:
    rows = collect_drift(root, from_ref, to_ref)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    summary = ", ".join(f"{name}: {counts[name]}" for name in sorted(counts))
    _write(
        output / "FRONTEND_DRIFT.md",
        "# Frontend drift record\n\n"
        f"**From candidate baseline:** `{from_ref}`  \n"
        f"**To current program baseline:** `{to_ref}`\n\n"
        f"**Changed frontend-adjacent paths:** {len(rows)}\n\n"
        f"**Review classes:** {summary}\n\n"
        "A direct candidate collision means both the candidate implementation and current Sonder changed the path after the historical baseline. Such a file is always rebased by scoped intent; it is never copied wholesale from the candidate.\n\n"
        + _table(
            ("Status", "Path", "Review class", "Candidate collision", "Rebase rule"),
            ((row["status"], f"`{row['path']}`", row["classification"], row["candidate_collision"], "preserve current behavior; port scoped candidate intent only") for row in rows),
        ),
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def _storage_for_route(path: str) -> str:
    rules = (
        ("/api/auth", "host account/session tables"),
        ("/api/guest", "guest session/invite tables"),
        ("/api/chats", "chat/frame/world records and projections"),
        ("/api/turns", "turn/step/narration records"),
        ("/api/characters", "reusable character records"),
        ("/api/personas", "reusable persona records"),
        ("/api/lorebooks", "lorebook/entry/link records"),
        ("/api/library", "Library projection and reversible lifecycle metadata"),
        ("/api/extensions", "extension runtime/config/state/documents"),
        ("/api/providers", "provider/model configuration"),
        ("/api/ui", "UI language-pack projection"),
        ("/api/language-packs", "installed language-pack projection"),
        ("/api/maintenance", "checkpoint/maintenance operations"),
    )
    return next((store for prefix, store in rules if path.startswith(prefix)), "settings or derived server projection")


def _table(headers: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out.extend("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows)
    return "\n".join(out)


def write_artifacts(
    root: Path,
    output: Path,
    *,
    baseline_head: str,
    candidate_head: str,
) -> None:
    root = root.resolve()
    output = output.resolve()
    inventory = collect_inventory(root)
    payload = {
        "baseline_head": baseline_head,
        "candidate_head": candidate_head,
        **inventory,
    }
    _write(output / "baseline" / "source-inventory.json", json.dumps(payload, indent=2, sort_keys=True))

    _write(
        output / "CAPABILITY_LEDGER.md",
        "# Current capability ledger\n\n"
        "Evidence map for the completed replacement; WP14 is the release authority.\n\n"
        + _table(
            ("ID", "Capability", "Current authority / evidence", "Owner", "Mobile", "Disposition"),
            ((f"`{cid}`", name, source, owner, mobile, disposition) for cid, name, source, owner, mobile, disposition in CAPABILITIES),
        ),
    )

    surface_rows = []
    for entry in inventory["entries"]:
        surface_rows.append((
            f"`{entry['path']}`",
            ", ".join(f"`{item}`" for item in entry["scripts"]) or "none",
            ", ".join(f"`{item}`" for item in entry["styles"]) or "none",
            len(entry["dom_ids"]),
        ))
    _write(
        output / "SURFACE_INVENTORY.md",
        "# Current entry and surface inventory\n\n"
        f"Generated from `{baseline_head}`.\n\n"
        + _table(("Entry", "Scripts", "Styles", "DOM IDs"), surface_rows),
    )

    _write(
        output / "API_PERSISTENCE_MAP.md",
        "# Current API and persistence boundary map\n\n"
        "The storage column names server authority; it does not authorize direct client persistence.\n\n"
        + _table(
            ("Method", "Route", "Server authority", "Source"),
            ((row["method"], f"`{row['path']}`", _storage_for_route(row["path"]), f"`{row['source']}`") for row in inventory["routes"]),
        ),
    )

    html_ids = sorted({item for entry in inventory["entries"] for item in entry["dom_ids"]})
    referenced_ids = sorted({row["id"] for row in inventory["dom_references"]})
    _write(
        output / "GLOBAL_DOM_INVENTORY.md",
        "# Current browser-global and DOM integration inventory\n\n"
        "Classic declarations are potential shared-global bindings because current scripts are not modules.\n\n"
        "## Browser globals\n\n"
        + _table(("Name", "Kind", "Source"), ((f"`{row['name']}`", row["kind"], f"`{row['source']}`") for row in inventory["browser_globals"]))
        + "\n\n## DOM IDs declared by entries\n\n"
        + ", ".join(f"`{item}`" for item in html_ids)
        + "\n\n## DOM IDs referenced by classic scripts\n\n"
        + ", ".join(f"`{item}`" for item in referenced_ids),
    )

    _write(
        output / "THEME_EXTENSION_INVENTORY.md",
        "# Current theme, localization, and extension inventory\n\n"
        f"**Themes:** {', '.join(f'`{item}`' for item in inventory['themes']) or 'none detected'}\n"
        f"**CSS custom properties:** {len(inventory['css_custom_properties'])}\n\n"
        f"**UI catalog keys:** {len(inventory['ui_catalog_keys'])}\n\n"
        "## Extension routes\n\n"
        + _table(("Method", "Route", "Source"), ((row["method"], f"`{row['path']}`", f"`{row['source']}`") for row in inventory["extension_routes"])),
    )

    _write(
        output / "UNBUILT_UI_OWNERSHIP.md",
        "# UI-related unfinished-work ownership\n\n"
        "This is a cross-reference only. The cited sections in `docs/UNBUILT.md` remain the authority and are not closed by receiving a UI work-package owner.\n\n"
        + _table(
            ("UNBUILT", "Player-facing concern", "Replacement owner", "Replacement boundary"),
            ((f"`{section}`", concern, owner, boundary) for section, concern, owner, boundary in UNBUILT_UI_OWNERSHIP),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-head", required=True)
    parser.add_argument("--candidate-head", required=True)
    parser.add_argument("--drift-from")
    parser.add_argument("--drift-to")
    args = parser.parse_args()
    output = args.output or args.root / "docs" / "design" / "sonder-ui-replacement"
    write_artifacts(
        args.root,
        output,
        baseline_head=args.baseline_head,
        candidate_head=args.candidate_head,
    )
    if bool(args.drift_from) != bool(args.drift_to):
        parser.error("--drift-from and --drift-to must be supplied together")
    if args.drift_from and args.drift_to:
        write_drift_artifact(output, args.root, args.drift_from, args.drift_to)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
