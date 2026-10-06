# Superseded links: what was measured before they shipped (2026-10-05)

The concept lab's superseded links ([`CONCEPT_LAB_2026_09_30.md`](CONCEPT_LAB_2026_09_30.md)
§10-13) carried into the engine as `memories.supersedes` and
`mind/memory_links.py` (Design.md, "A later memory that changes a recalled one
comes with it"). Four things were measured on the way, each with a script in
`tools/concept_lab/` (`links_*.py`; how to rerun is in each docstring). The
decision model throughout is Jev 1.13 on the owner's OpenRouter route, asked as
the lab asked it: state "YOU ARE <name>.", one yes/no question a pair.

## 1. The question's wording (`links_wording.py`)

Five wordings over the 30 labelled (outdated, current) pairs of
`probes_large.json`, plus each current row's ten most alike older rows by TF-IDF
(81 more pairs, mostly not links):

| wording | labelled pairs linked | other candidates linked |
|---|---|---|
| the lab's: "...change something the older one states as true -- a figure, a state, where something is, who has it, whether something still holds?" | **25/30** | 14/81 |
| the same list marked "for instance" | 19/30 | 9/81 |
| the list left open ("..., or anything else it states?") | 19/30 | 11/81 |
| "Answer yes whatever it changes -- ..." | 25/30 | 23/81 |
| the class alone | 11/30 | 5/81 |

The named causes carry the recall, and marking them as examples costs a fifth
of it -- a measured exception to CLAUDE.md's "mark examples as illustrations",
the same direction as the walk-stop question of 2026-09-28. The lab's wording
shipped; its precision is the lab's hand-judged 19 of 30. The Japanese question
takes the pack's own "if any one of these holds, answer yes" form, unprobed on
Japanese passages.

## 2. How many older memories to ask about (`links_candidates.py`)

On the large lab bank embedded with the engine's own vectors (pplx-embed, the
lab's `embed_bank.py`), the rank of the older row among the newer row's older
rows by cosine of the stored content vectors:

| | top 5 | top 10 | top 20 |
|---|---|---|---|
| outdated row of a labelled pair (30) | 17 | **22** | 26 |
| the lab's Jev-confirmed links (196) | 147 | **179** | -- |

The lab's TF-IDF top 5 held 13 of the 30. `LINK_CANDIDATES` is 10.

## 3. The question on real banks (`links_replay.py`)

Every turn memory of one mind, as if newly minted, against its ten most alike
strictly older turn memories (engine.db read-only):

| bank | turn memories | questions | yes |
|---|---|---|---|
| chat 64, the Doctor (170 turns, long scene descriptions) | 327 | 3,258 in 20.5 s (0.55 s a 100-question request) | **24%** |
| chat 161, Sarah Moon (short rows, the one-memory format) | 23 | 230 | **10%** |

Read as fiction, about 3 to 5 links in 8 mark a fact gone stale ("a figure with
a finger on the button" -> "she lifts her hand ... I'm Hinami"); the rest pair
two moments of one scene, since a later scene changes "where something is"
almost by definition. A weak link costs payload, never truth: the row it brings
is this mind's own later memory.

## 4. How often recall brings one in (`links_pull_rate.py`)

The shipped pull rule -- every row that changed a recalled row, newest first,
then the newest row its links reach (review round 5: following the chain to its
end alone dropped the row that actually made the change; on the lab's graph the
direct successors held an answer for 12 of 23 outdated rows, the chain's end for
10) -- applied to chat 64's replayed graph: of the linkable rows older than the
8-turn recent window, the share that would bring at least one row the window
does not hold.

| point in the story | older rows | would bring a successor | newest brought, turns ahead |
|---|---|---|---|
| T=40 | 67 | 48% | 10 |
| T=80 | 143 | 57% | 14 |
| T=120 | 223 | 65% | 24 |
| T=170 | 319 | 63% | 43 |

Chat 161: 31%. So on a long bank a full recall of 30 reaches `PULL_CAP` (6) on
nearly every beat -- six more of this mind's own memories, about 6,000
characters, beside the 30. The cap, the candidate count and the quote length are
the owner's to set.
