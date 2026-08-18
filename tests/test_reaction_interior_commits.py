"""What a character works out while REACTING has to survive the beat.

Live, chats 70/71/72 (three branches of one story, same turn idx 16): the
Doctor adopted a project -- "Reach Kaa Sama's shrine near Kyoto and
investigate the kitsune lineage's connection to the anomaly", with a genuine
external criterion, exactly the shape the adoption deliberation is built to
accept. `interior.projects` is empty in all three.

`agents/loops.py` writes a reaction round's result to `ctx.reaction_results`
(the interaction loop merges into `ctx.character_results` instead), and
`commit.py` read only `ctx.character_results`. Nothing anywhere read
`reaction_results`, so everything a reacting mind worked out was dropped --
silently, because `apply_project_ops` was handed an empty list and had
nothing to warn about.

Measured across the 82 stored reaction beats in the corpus: EVERY ONE
carried interior content that never reached commit -- 159 mind_model_updates,
93 relationship_updates, 20 belief_updates, 18 remember_lines, 12
association_updates. A reaction is the beat with the most immediate pressure
on a character, and they were forming theories about people, revising
relationships and marking things worth remembering into nothing.
"""

from __future__ import annotations

from agents.common import _merge_character_results


class TestTheMergeKeepsEveryAccumulatingField:
    """`_merge_character_results` unions the list fields so no round's work is
    lost. `project_ops` was not in that list -- so a character who adopted a
    project in round 0 and spoke again in round 1 lost it, which is the same
    bug as the reaction drop in miniature and inside a single loop."""

    def test_project_ops_survive_an_later_round(self):
        earlier = {"project_ops": [{"op": "adopt", "project": "Find the well",
                                    "satisfied_when": "the village draws from it"}]}
        later = {"sequence": [{"type": "speech", "text": "Right."}]}

        merged = _merge_character_results(earlier, later)

        assert merged["project_ops"] == earlier["project_ops"], (
            "a project adopted in an earlier round was dropped by the merge")

    def test_a_later_round_may_add_its_own(self):
        earlier = {"project_ops": [{"op": "adopt", "project": "A"}]}
        later = {"project_ops": [{"op": "displace", "id": "p1",
                                  "reason": "the road closed"}]}

        merged = _merge_character_results(earlier, later)

        assert len(merged["project_ops"]) == 2

    def test_every_schema_list_field_the_mind_emits_is_unioned(self):
        """The general rule, so the next field added does not repeat this.
        Any `*_ops`/`*_updates` field a character may emit accumulates across
        rounds; dropping one loses a mind's work with no warning anywhere."""
        from llm import schemas

        model = schemas.SCHEMA_MAP["character"]
        fields = list(getattr(model, "model_fields", None)
                      or getattr(model, "__fields__"))
        accumulating = [f for f in fields
                        if f.endswith("_ops") or f.endswith("_updates")]
        earlier = {f: [{"probe": f}] for f in accumulating}

        merged = _merge_character_results(earlier, {"sequence": []})

        missing = [f for f in accumulating if not merged.get(f)]
        assert missing == [], f"dropped by the merge: {missing}"


class TestAReactingMindIsStillAMind:
    def test_commit_reads_the_reaction_round_too(self):
        """The live drop. Commit resolved a character's beat result from
        `character_results` alone, so a mind that only REACTED committed
        nothing of what it worked out."""
        import inspect

        from persist import commit
        body = inspect.getsource(commit.prepare_character_commits) \
            if hasattr(commit, "prepare_character_commits") else ""
        # The merge lives in prepare_memory_commit (commit_memory since the
        # split); the function source survives the move.
        source = body or inspect.getsource(commit.prepare_memory_commit)
        assert "reaction_results" in source, (
            "commit still never reads reaction_results")

    def test_the_two_sources_are_merged_not_chosen_between(self):
        """A character can both act and react in one beat. Taking one result
        and discarding the other loses whichever half it did not pick."""
        reacted = {"project_ops": [{"op": "adopt", "project": "Find the well"}],
                   "mind_model_updates": [{"subject": "Mara"}]}
        acted = {"sequence": [{"type": "speech", "text": "Later."}],
                 "mind_model_updates": [{"subject": "The Doctor"}]}

        merged = _merge_character_results(reacted, acted)

        assert merged["project_ops"], "the reaction's project was discarded"
        assert len(merged["mind_model_updates"]) == 2
        assert merged["sequence"] == acted["sequence"]
