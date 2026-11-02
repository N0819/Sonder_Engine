#!/usr/bin/env python3
"""Regenerate docs/CODE_MAP.md from the current source tree.

The output is intentionally structural rather than interpretive: module imports,
large top-level functions, FastAPI routes, database tables, and frontend section
markers. Keep durable architectural explanations in AGENTS.md and docs/guides/PIPELINE.md.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "CODE_MAP.md"

MODULE_PURPOSES = {
    "agents": "Backward-compatible facade for the role-specific agent package.",
    "agents.character": "Private character decision agent.",
    "agents.common": "Facade over the agents/common_* siblings (split 2026-11-01): shared normalization, lore, delivery, and perception helpers.",
    "agents.common_base": "Leaf of the common family: the 'agents.common' pack lookup, coercion, quote/typography folding, markup stripping, English third-person morphology.",
    "agents.common_llm": "The model-call seam (_agent_json) and JSON recovery (jparse, the miscounted-closer mender).",
    "agents.common_names": "Names in any script: name tokens and recognition, sentence splitting, subject/pronoun tracking, the stranger-label grammar.",
    "agents.common_cast": "The registered cast inside the scene: identity keys, rooms, spelling policy, entity reconciliation, position canonicalisation, exclusion lists.",
    "agents.common_bodies": "What one observer perceives of a body: attire views, exposure, extra parts, per-region visibility, containment spelling, the delivery gate.",
    "agents.common_rooms": "What a room holds for a perceiver: crowds, chatter, couriers and notices, the room's prose, the Director's lore slice, the payload room set.",
    "agents.common_figures": "Who stands where this beat: charter and presence figures, creature stances, planned figures, the player's room ladder and resolver, the aperture.",
    "agents.common_identity": "The identity floor on payloads and views: observer label functions, the name scrub, act-surface admission, the last-pass identity scrub.",
    "agents.common_acts": "What a declared element is: act classification, communicative-act vocabulary, claim dispositions, target binding, the reaction/resolution gates.",
    "agents.common_sequence": "A declared beat as the engine holds it: speech provenance, stage-direction excision, norm_sequence, duplicate collapse, event ids, the player token.",
    "agents.common_beat": "The beat's bookkeeping around its minds: the plan invariant, micro-round merging, who speaks and reacts next, declared goals, asserted state.",
    "agents.common_scrubs": "Prose repair passes: the repeated-quote cap, dangling-speech healing, the player-echo strip, the invented-dialogue scrub, sentence dedupe.",
    "agents.common_authority": "Director/player authority checks on resolved prose and contacts, the presence-knowledge floor, the player-authority ladder on claims.",
    "agents.common_views": "Deterministic sentences composed into a view: muffling, tone, self-reference and second-person rewriting, observable predicates, the residue view.",
    "agents.common_narration": "The narrator's own voice, measured: tics, rhythm, recycled shingles, person/tense counts, the pronoun-fidelity check.",
    "agents.common_fidelity": "The narrator page against its records: event order, quote/action attribution, position/portal/attire fidelity, _check_narrator_fidelity.",
    "agents.composer": "Facade over the agents/composer_* siblings (split 2026-11-01): the view renderer every perception path calls into.",
    "agents.composer_common": "Leaf of the composer family: the typed IR (Percept, RenderedView), ledger keys, compositor-pack accessors, shared phrase splicers, _safe_renderer.",
    "agents.composer_person": "Grammatical person: a third-person line turned into the observer's second person for the view and first person for memory.",
    "agents.composer_figures": "Who is here and what this observer calls them: referring expressions, the stranger-label ladder, the sight-gated display map, presence percepts.",
    "agents.composer_bodies": "Percepts about a body: poses and referents, extra parts, appearance, tells, the observer's own state, ears, contacts, bare regions, non-awake residue.",
    "agents.composer_speech": "A line as one observer receives it: concealment, addressee, the hearing gate and its rescues, voice/tone/register, silence, described communication.",
    "agents.composer_acts": "An act, a substance transfer and a crossing as one observer receives them: concealment, heard movement, the sight grade, the first-person copy.",
    "agents.composer_fields": "The place as standing sensory state: room, light and sound, authored and distant sounds, scent, a walk underway, weather, thunder, felt shakes.",
    "agents.composer_landscape": "Far sight: vistas, far places and far looks as lines (landscape_lines), realised in any pack's words (compose_landscape_line).",
    "agents.composer_things": "Things in the room: placed or in hand, readings, crowds/couriers/notices, chatter, the micro-round delivery.",
    "agents.composer_standing": "Standing verdicts against the observer's ledger, what leads the beat, habituation, beat order, carried voices, observations_from_render.",
    "agents.composer_render": "The English reference VIEW renderer: standing and event sentences, the presence roll-call, _render_view_english slot ordering, render_view.",
    "agents.composer_episode": "The English reference EPISODE renderer (memory mode): first-person sentences, what files as memory, render_episode, episode_signature.",
    "agents.perception": "Facade over the agents/perception_* siblings (split 2026-11-01): the deterministic observer views at opening, onset and outcome.",
    "agents.perception_common": "Leaf helpers every other sibling reads: the active pack's recognizer tables and the one sentence splitter, the observer-identity test, the human-seat test, the step's player-room stamp, and the per-ob.",
    "agents.perception_bodies": "A body's outward form: the turn's disguise and transformation reads (and their caches), what a disguise conceals and its tripwire terms, authored extra parts, card scents and body descriptions, attire.",
    "agents.perception_senses": "What reaches one observer's eyes and ears: the per-source sight and channel maps, sight detail and plain view, rooms behind and in view, the per-stage sound field, sleepers' hearing, ear cover and bla.",
    "agents.perception_conduct": "Readers of this beat's declared conduct: rapid movement and the open-group continuity rescue, where a line was said relative to a declared walk, a crossing's legs and the channel to every leg, the bea.",
    "agents.perception_identity": "Who and what an observer may name: the identity roster and the chat's identity space, worn roles and charter titles, recognition and attributed labels, stranger labels and self-forms, presence bodies .",
    "agents.perception_scrub": "What a composed view may say and how it is finished: the self-narration strip and its quote-safe wrapper, the identity scrubs over act surfaces, authored prose and episodes, the composer tripwires and.",
    "agents.perception_stream": "The outcome beat as one ordered stream and the signs placed in it: settled declarations, causal spans and restored lines, the world-ordered stream, unanswered addresses, background beats, and the tell.",
    "agents.perception_standing": "One observer's standing state and its assembler: things read by hand, station or look, visible features, things and openings (with beam-lit rooms), scents, gated ambient events, the bare-region rows, .",
    "agents.perception_opening": "The opening pass: `perception_establish` and its composer region (`_composer_establish`, `_composer_establish_views`, the opening's quoted lines).",
    "agents.perception_onset": "The action-onset pass (pass 1): `perception_act`, its composer region (`_composer_act`, `_composer_act_views`), and `beat_player_rooms`, runtime's early reading of the same declaration.",
    "agents.perception_outcome_views": "The outcome pass's composer region: `_composer_outcome` (sweep stamp, read pass) and `_composer_outcome_views`, the 1,309-line per-observer assembler moved whole.",
    "agents.perception_outcome_stage": "The outcome stage entry point `perception_outcome`: composes the beat scene once, enriches the dialogue log, builds every perceiver and hands off to `_composer_outcome`.",
    "agents.director": "Scene establishment, player interpretation, and objective resolution.",
    "agents.loops": "Reaction loops, interaction rounds, and deterministic micro-perception.",
    "agents.mapping": "Lore routing, cached recall, and retrieval staging.",
    "agents.narration": "Player-facing narration agent.",
    "agents.runtime": "Pipeline plans, dispatch, streaming, cancellation, resume, and reruns.",
    "agents.storage": "Step and active-variant persistence helpers.",
    "web.app": "FastAPI application assembly, resource CRUD, turn control, and streaming endpoints.",
    "web.auth_routes": "Typed host-authentication HTTP routes and cookie transport.",
    "persist.chat_archive": "Typed, atomic chat archive export/import service and HTTP routes.",
    "story.character_schema": "Versioned character/persona defaults, normalization, accessors, and export payloads.",
    "persist.checkpoints": "Whole-chat snapshots and checkpoint restore orchestration.",
    "persist.commit": "Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name.",
    "persist.commit_common": "Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation.",
    "persist.commit_place_graph": "Per-mind durable place graph and per-beat spatial experience.",
    "persist.commit_destruction": "Single- and multi-book destruction cascades, retirement, and latency-gated news.",
    "persist.commit_room_registry": "Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning.",
    "persist.commit_attire": "The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff.",
    "persist.commit_entities": "world_entities projection of the scene commit, awareness gate, disguise supersession.",
    "persist.commit_ledgers": "The world-pressure ledger.",
    "persist.commit_mapping": "Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser.",
    "persist.commit_background": "Background presences: tracking, identity folding, the reactor gate, promotion to cast.",
    "persist.commit_scene_state": "The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance.",
    "persist.commit_mechanics": "Transit/news sweeps, the world-event spine, information carriers, cast changes.",
    "persist.commit_memory": "Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them.",
    "persist.commit_memory_write": "The durable memory write and its out-of-band consolidation twin.",
    "core.db": "SQLite schema, migrations, connection management, transactions, and key/value world access.",
    "story.importers": "Native and AI-assisted character, persona, and lorebook import/generation.",
    "llm.llm_quality": "Strict JSON parsing, schema validation, and model-assisted repair.",
    "core.logging_utils": "Structured timing and observability helpers.",
    "mind.memory": "Facade re-exporting every mind.memory_* name; holds no domain code of its own.",
    "mind.memory_common": "Leaf helpers shared by every memory domain: vocabularies, blob/vector codecs, FTS query, cosine.",
    "mind.memory_lorebooks": "The lorebook graph: hierarchy, links, inheritance modes, per-chat attachment and weights.",
    "mind.memory_write": "How a memory becomes a row: normalisation, extraction, FTS mirror, the upsert, and the embedding-repair thread.",
    "mind.memory_read": "The one seam a mind reads its own memory through, and the host reads that deliberately cross characters.",
    "mind.memory_retrieval": "Hybrid retrieval: lexical and vector rankings fused by RRF, tilted by mood and importance, plus unbidden recall.",
    "mind.memory_summaries": "Autobiographical, hearsay and surmise summaries: search, support sets, windowed consolidation and backfill.",
    "mind.memory_context": "The character memory payload: where retrieval, summaries and active state become one context.",
    "mind.memory_lore_entries": "Lore entries: add/update/delete, embedding stamps and health, search_lore, per-character knowledge scoping.",
    "mind.memory_snapshot": "Checkpoint and archive: vector addressing, the prepare/apply restore split, memory and lorebook dump/restore.",
    "mind.memory_relationships": "The relationship graph: axis deltas from conduct and from inference, and the history behind them.",
    "mind.memory_vectors": "Rebuilding vectors after the embedding model changes: bank status, the rebuild, and its background run.",
    "mind.memory_inference": "Belief confidence at mint and at abandonment, and reconciliation across a mind's inferences.",
    "core.pipeline_context": "Typed mutable context passed through a turn pipeline.",
    "persist.pipeline_trace": "Privacy-conscious export, validation, and offline replay of persisted pipeline history.",
    "llm.prompt_cache": "Provider-specific prompt-cache helpers.",
    "llm.prompts": "Default system prompts and prompt preset access.",
    "llm.providers": "Provider selection, retries, streaming, cancellation, model listing, and embeddings.",
    "story.scene": "Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge.",
    "llm.schemas": "Pydantic output contracts and semantic validation for agent payloads.",
    "world.spatial": "Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic.",
    "world.spatial_orientation": "Bearing math and reciprocal spatial-edge normalization.",
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def source_paths() -> list[Path]:
    paths = []
    for pkg in ("core", "llm", "world", "mind", "story",
                "dressing", "persist", "web"):
        paths.extend((ROOT / pkg).glob("*.py"))
    agents_dir = ROOT / "agents"
    if agents_dir.exists():
        paths.extend(agents_dir.rglob("*.py"))
    return sorted(paths)


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def display_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def resolve_import(path: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    current = module_name(path).split(".")
    package = current if path.name == "__init__.py" else current[:-1]
    keep = max(0, len(package) - (node.level - 1))
    parts = package[:keep]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts) or None


def md(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def parse_module(path: Path, local_modules: set[str]) -> dict:
    # Read ONCE: the line count below used to read the file a second time.
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    local_roots = {name.split(".")[0] for name in local_modules}
    imports: set[str] = set()
    functions: list[tuple[str, int, int, bool]] = []
    classes: list[tuple[str, int, int]] = []
    routes: list[tuple[str, str, str, int]] = []
    router_prefixes: dict[str, str] = {}

    # Route decorators carry only the path relative to their APIRouter.
    # Record literal local prefixes first so the generated map describes the
    # actual public URL instead of turning /api/auth/login into /login.
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        call_name = value.func.id if isinstance(value.func, ast.Name) else None
        if call_name != "APIRouter":
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        prefix = ""
        for keyword in value.keywords:
            if (
                keyword.arg == "prefix"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                prefix = keyword.value.value
                break
        for name in names:
            router_prefixes[name] = prefix

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                if root_name in local_roots:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imported = resolve_import(path, node)
            if imported and imported.split(".")[0] in local_roots:
                imports.add(imported)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            functions.append((
                node.name,
                node.lineno,
                end - node.lineno + 1,
                isinstance(node, ast.AsyncFunctionDef),
            ))
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if not isinstance(func, ast.Attribute) or func.attr not in HTTP_METHODS:
                    continue
                if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                    continue
                route_path = str(decorator.args[0].value)
                if isinstance(func.value, ast.Name):
                    route_path = (
                        router_prefixes.get(func.value.id, "") + route_path
                    )
                routes.append((func.attr.upper(), str(route_path), node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            classes.append((node.name, node.lineno, end - node.lineno + 1))

    # Extracted service objects may register bound methods explicitly because
    # decorators cannot reference an instance that is injected later by the
    # application assembly layer. Only a file that spells the call is walked
    # (one engine file did, 2026-11-01): a whole-tree walk of every module
    # for one method name was a third of the generator's time, and `make
    # check` generates the map more than once.
    for node in (ast.walk(tree) if "add_api_route" in source else ()):
        if not isinstance(node, ast.Call):
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_api_route"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        handler = node.args[1]
        if isinstance(handler, ast.Attribute):
            handler_name = handler.attr
        elif isinstance(handler, ast.Name):
            handler_name = handler.id
        else:
            handler_name = "<callable>"
        methods = ["GET"]
        for keyword in node.keywords:
            if keyword.arg != "methods":
                continue
            if isinstance(keyword.value, (ast.List, ast.Tuple, ast.Set)):
                parsed = [
                    item.value.upper()
                    for item in keyword.value.elts
                    if isinstance(item, ast.Constant)
                    and isinstance(item.value, str)
                ]
                if parsed:
                    methods = parsed
        for method in methods:
            routes.append(
                (method, node.args[0].value, handler_name, node.lineno)
            )

    return {
        "imports": sorted(imports),
        "functions": functions,
        "classes": classes,
        "routes": routes,
        "lines": len(source.splitlines()),
    }


def database_tables() -> list[tuple[str, list[str]]]:
    text = (ROOT / "core" / "db.py").read_text(encoding="utf-8")
    match = re.search(r'SCHEMA\s*=\s*"""(.*?)"""', text, re.S)
    if not match:
        return []
    tables: list[tuple[str, list[str]]] = []
    pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\);",
        re.I | re.S,
    )
    for table_match in pattern.finditer(match.group(1)):
        columns: list[str] = []
        for line in table_match.group(2).splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(("PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CHECK", "CONSTRAINT")):
                continue
            columns.append(line.split()[0].rstrip(","))
        tables.append((table_match.group(1), columns))
    return tables


def js_map(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    text = path.read_text(encoding="utf-8")
    sections: list[tuple[int, str]] = []
    functions: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        section = re.match(r"\s*//\s*-{2,}\s*(.*?)\s*-*\s*$", line)
        if section and section.group(1):
            sections.append((line_no, section.group(1)))
        function = re.match(r"\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", line)
        if function:
            functions.append((line_no, function.group(1)))
    return sections, functions


class StalePurposeKeys(Exception):
    """`MODULE_PURPOSES` names a module that does not exist."""


def check_purpose_keys(local_modules: set[str]) -> None:
    """Every purpose must belong to a module, or the table is silently empty.

    `MODULE_PURPOSES` is keyed by module name and read with `.get(name, "")`,
    so a key that matches nothing renders as a blank Purpose cell and reports
    nothing. The 2026-08 package move made 33 of 43 keys stale in one commit —
    bare `commit`, `db`, `spatial` became `persist.commit`, `core.db`,
    `world.spatial` — and 100 of 110 rows in `docs/CODE_MAP.md` lost their
    Purpose column with no diff to read, because `check_generated_map`
    regenerates the file and compares: both sides lost the purposes together.

    A hand-kept list of module names is exactly what a tree move breaks, so the
    generator refuses to produce a map from a table it cannot resolve. The
    tolerance that hid this — `.get(name, "")` — stays: a module with no
    purpose is normal, an unowned purpose is not.
    """
    tails: dict[str, list[str]] = {}
    for name in local_modules:
        tails.setdefault(name.rpartition(".")[2], []).append(name)
    stale = []
    for key in sorted(MODULE_PURPOSES):
        if key in local_modules:
            continue
        moved = sorted(tails.get(key.rpartition(".")[2], []))
        stale.append("%s%s" % (key, " (now %s)" % ", ".join(moved) if moved else ""))
    if stale:
        raise StalePurposeKeys(
            "MODULE_PURPOSES keys match no module, so their rows would render "
            "an empty Purpose column: " + "; ".join(stale))


def generate() -> str:
    paths = source_paths()
    local_modules = {module_name(path) for path in paths}
    check_purpose_keys(local_modules)
    modules = [(path, parse_module(path, local_modules)) for path in paths]
    lines: list[str] = [
        "# Generated Code Map",
        "",
        "> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.",
        "",
        "## Python modules",
        "",
        "| Module | Lines | Purpose | Local dependencies |",
        "|---|---:|---|---|",
    ]
    for path, info in modules:
        name = module_name(path)
        lines.append(
            f"| `{display_path(path)}` | {info['lines']} | {md(MODULE_PURPOSES.get(name, ''))} | "
            f"{', '.join(f'`{dependency}`' for dependency in info['imports']) or '—'} |"
        )

    lines += ["", "## Largest top-level functions", ""]
    for path, info in modules:
        largest = sorted(info["functions"], key=lambda item: item[2], reverse=True)[:8]
        if not largest:
            continue
        lines += [f"### `{display_path(path)}`", "", "| Function | Start | Size |", "|---|---:|---:|"]
        for name, start, size, is_async in largest:
            prefix = "async " if is_async else ""
            lines.append(f"| `{prefix}{name}()` | {start} | {size} lines |")
        lines.append("")

    route_rows = []
    for path, info in modules:
        route_rows.extend(
            (method, route, func, line, display_path(path))
            for method, route, func, line in info["routes"]
        )
    if route_rows:
        lines += ["## FastAPI routes", "", "| Method | Path | Handler | Source |", "|---|---|---|---|"]
        for method, route, func, line, source in sorted(route_rows, key=lambda item: (item[1], item[0])):
            lines.append(f"| {method} | `{md(route)}` | `{func}()` | `{source}:{line}` |")
        lines.append("")

    lines += ["## Database tables", "", "| Table | Columns |", "|---|---|"]
    for table, columns in database_tables():
        lines.append(f"| `{table}` | {', '.join(f'`{column}`' for column in columns)} |")
    lines.append("")

    js_paths = sorted((ROOT / "static" / "js").glob("*.js"))
    if js_paths:
        lines += ["## Frontend JavaScript", ""]
        for path in js_paths:
            sections, functions = js_map(path)
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            lines += [f"### `static/js/{path.name}` ({line_count} lines)", ""]
            if sections:
                lines.append("Sections: " + "; ".join(f"{name} (`:{line}`)" for line, name in sections) + ".")
                lines.append("")
            if functions:
                lines.append("Declared functions: " + ", ".join(f"`{name}()`" for _, name in functions) + ".")
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generate(), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
