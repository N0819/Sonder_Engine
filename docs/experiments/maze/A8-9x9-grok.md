# The maze runs, move by move

Arm A8: 9x9 Kruskal, character on x-ai/grok-4.20, every fix from the 2026-07-28 session. Run 5 is an exact optimal traversal.

Numbers in each grid are the beat a room was **first** entered. `*` marks the optimal route where he never went, `X` the goal.

## The maze

9×9 kruskal, braid 0.0, seed `20260727` — 81 rooms, 21 junctions, 25 dead ends, optimal **20 moves**.

Traps: 60 rooms off-route, 16 false branches 3+ deep, worst 15 rooms, mean 5.3.

Code state: `1e8a77e` · `--agent llm --preset fast --algo kruskal --size 9 --runs 5 --max-steps 60 --verbose --grid --go --state /tmp/claude-1000/-home-nathan-Documents-Fiction-improved-Sonder-Engine-alpha4-1-2-dev/9a72de1b-6c1a-493a-b16b-7ed54f515889/scratchpad/arm9.state.json --think /tmp/claude-1000/-home-nathan-Documents-Fiction-improved-Sonder-Engine-alpha4-1-2-dev/9a72de1b-6c1a-493a-b16b-7ed54f515889/scratchpad/arm9_think.log --out /tmp/claude-1000/-home-nathan-Documents-Fiction-improved-Sonder-Engine-alpha4-1-2-dev/9a72de1b-6c1a-493a-b16b-7ed54f515889/scratchpad/arm9_runs.jsonl`

```
+---+---+---+---+---+---+---+---+---+
|  *   *|                   |   |   |
+   +   +   +---+---+   +---+   +   +
|   |  *|   |       |       |       |
+   +   +---+---+   +   +---+---+   +
|   |  *            |               |
+---+   +---+---+---+---+---+   +---+
|      *|   |   |   |       |       |
+---+   +   +   +   +   +---+   +---+
|      *   *    |               |   |
+   +---+   +   +---+   +---+---+   +
|   |  *   *|   |       |           |
+   +   +---+---+---+   +---+   +   +
|   |  *   *   *    |   |   |   |   |
+   +---+---+   +---+   +   +   +   +
|           |  *|   |  *   *|   |   |
+   +   +   +   +   +   +   +   +---+
|   |   |   |  *   *   *|  *   *   *|
+---+---+---+---+---+---+---+---+---+
```

Optimal route:

```
r0000 r0001 r0101 r0201 r0301 r0401 r0402 r0502 r0501 r0601 r0602 r0603 r0703 r0803 r0804 r0805 r0705 r0706 r0806 r0807 r0808
```


---

## Run 1 — did not arrive (58 moves, optimal 20)

`backtracks 33` · `reversals 8` · `idle 2` · `rooms seen 28/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   2|                   |   |   |
+   +   +   +---+---+   +---+   +   +
| 46|  5|   | 37  36|       |       |
+   +   +---+---+   +   +---+---+   +
|   |  6  33  34  35|               |
+---+   +---+---+---+---+---+   +---+
|      7|   | 12|   |       |       |
+---+   +   +   +   +   +---+   +---+
| 18   8  10  11|               |   |
+   +---+   +   +---+   +---+---+   +
| 19| 57  56| 14|       |           |
+   +   +---+---+---+   +---+   +   +
| 20| 58  59  60    |   |   |   |   |
+   +---+---+   +---+   +   +   +   +
| 21  22  23| 61|   |       |   |   |
+   +   +   +   +   +   +   +   +---+
|   |   |   |           |          X|
+---+---+---+---+---+---+---+---+---+
```

| beat | to | dir | |
|---:|---|---|---|
| 1 | `r0001` | east | **on route** |
| 2 | `r0000` | west | rejoins route, revisit, reversal |
| 3 | `r0001` | east | **on route**, revisit, reversal |
| 4 | `r0101` | south | **on route** |
| 5 | `r0201` | south | **on route** |
| 6 | `r0301` | south | **on route** |
| 7 | `r0401` | south | **on route** |
| 8 | `r0401` | — | stayed put |
| 9 | `r0402` | east | **on route** |
| 10 | `r0403` | east | — |
| 11 | `r0303` | north | DEAD END |
| 12 | `r0403` | south | revisit, reversal |
| 13 | `r0503` | south | DEAD END |
| 14 | `r0403` | north | revisit, reversal |
| 15 | `r0402` | west | rejoins route, revisit |
| 16 | `r0401` | west | rejoins route, revisit |
| 17 | `r0400` | west | — |
| 18 | `r0500` | south | — |
| 19 | `r0600` | south | — |
| 20 | `r0700` | south | — |
| 21 | `r0701` | east | — |
| 22 | `r0702` | east | — |
| 23 | `r0701` | west | revisit, reversal |
| 24 | `r0700` | west | revisit |
| 25 | `r0600` | north | revisit |
| 26 | `r0500` | north | revisit |
| 27 | `r0500` | — | stayed put |
| 28 | `r0400` | north | revisit |
| 29 | `r0401` | east | rejoins route, revisit |
| 30 | `r0301` | north | rejoins route, revisit |
| 31 | `r0201` | north | rejoins route, revisit |
| 32 | `r0202` | east | — |
| 33 | `r0203` | east | — |
| 34 | `r0204` | east | — |
| 35 | `r0104` | north | — |
| 36 | `r0103` | west | DEAD END |
| 37 | `r0104` | east | revisit, reversal |
| 38 | `r0204` | south | revisit |
| 39 | `r0203` | west | revisit |
| 40 | `r0202` | west | revisit |
| 41 | `r0201` | west | rejoins route, revisit |
| 42 | `r0101` | north | rejoins route, revisit |
| 43 | `r0001` | north | rejoins route, revisit |
| 44 | `r0000` | west | rejoins route, revisit |
| 45 | `r0100` | south | — |
| 46 | `r0000` | north | rejoins route, revisit, reversal |
| 47 | `r0001` | east | **on route**, revisit |
| 48 | `r0101` | south | **on route**, revisit |
| 49 | `r0201` | south | **on route**, revisit |
| 50 | `r0301` | south | **on route**, revisit |
| 51 | `r0401` | south | **on route**, revisit |
| 52 | `r0402` | east | **on route**, revisit |
| 53 | `r0403` | east | revisit |
| 54 | `r0402` | west | rejoins route, revisit, reversal |
| 55 | `r0502` | south | **on route** |
| 56 | `r0501` | west | **on route** |
| 57 | `r0601` | south | **on route** |
| 58 | `r0602` | east | **on route** |
| 59 | `r0603` | east | **on route** |
| 60 | `r0703` | south | **on route** |


---

## Run 2 — reached the goal (51 moves, optimal 20)

`backtracks 16` · `reversals 6` · `idle 0` · `rooms seen 36/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   6|                   |   |   |
+   +   +   +---+---+   +---+   +   +
|  2|  7|   |       |       |       |
+   +   +---+---+   +   +---+---+   +
|  3|  8            |               |
+---+   +---+---+---+---+---+   +---+
|      9|   |   |   | 43  44|       |
+---+   +   +   +   +   +---+   +---+
| 11  10  27  28|     42        |   |
+   +---+   +   +---+   +---+---+   +
| 12| 31  30|   |     41|           |
+   +   +---+---+---+   +---+   +   +
| 13| 32  33  34    | 40|   |   |   |
+   +---+---+   +---+   +   +   +   +
| 14  15  16| 35|   | 39  49|   |   |
+   +   +   +   +   +   +   +   +---+
|   |   | 17| 36  37  38| 50  51  52|
+---+---+---+---+---+---+---+---+---+
```

| beat | to | dir | |
|---:|---|---|---|
| 1 | `r0100` | south | — |
| 2 | `r0200` | south | DEAD END |
| 3 | `r0100` | north | revisit, reversal |
| 4 | `r0000` | north | rejoins route, revisit |
| 5 | `r0001` | east | **on route** |
| 6 | `r0101` | south | **on route** |
| 7 | `r0201` | south | **on route** |
| 8 | `r0301` | south | **on route** |
| 9 | `r0401` | south | **on route** |
| 10 | `r0400` | west | — |
| 11 | `r0500` | south | — |
| 12 | `r0600` | south | — |
| 13 | `r0700` | south | — |
| 14 | `r0701` | east | — |
| 15 | `r0702` | east | — |
| 16 | `r0802` | south | DEAD END |
| 17 | `r0702` | north | revisit, reversal |
| 18 | `r0701` | west | revisit |
| 19 | `r0700` | west | revisit |
| 20 | `r0600` | north | revisit |
| 21 | `r0500` | north | revisit |
| 22 | `r0600` | south | revisit, reversal |
| 23 | `r0500` | north | revisit, reversal |
| 24 | `r0400` | north | revisit |
| 25 | `r0401` | east | rejoins route, revisit |
| 26 | `r0402` | east | **on route** |
| 27 | `r0403` | east | — |
| 28 | `r0402` | west | rejoins route, revisit, reversal |
| 29 | `r0502` | south | **on route** |
| 30 | `r0501` | west | **on route** |
| 31 | `r0601` | south | **on route** |
| 32 | `r0602` | east | **on route** |
| 33 | `r0603` | east | **on route** |
| 34 | `r0703` | south | **on route** |
| 35 | `r0803` | south | **on route** |
| 36 | `r0804` | east | **on route** |
| 37 | `r0805` | east | **on route** |
| 38 | `r0705` | north | **on route** |
| 39 | `r0605` | north | — |
| 40 | `r0505` | north | — |
| 41 | `r0405` | north | — |
| 42 | `r0305` | north | — |
| 43 | `r0306` | east | DEAD END |
| 44 | `r0305` | west | revisit, reversal |
| 45 | `r0505` | ? | revisit |
| 46 | `r0605` | south | revisit |
| 47 | `r0705` | south | rejoins route, revisit |
| 48 | `r0706` | east | **on route** |
| 49 | `r0806` | south | **on route** |
| 50 | `r0807` | east | **on route** |
| 51 | `r0808` | east | **on route**, DEAD END |


---

## Run 3 — did not arrive (60 moves, optimal 20)

`backtracks 16` · `reversals 5` · `idle 0` · `rooms seen 45/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   4| 50  49  48  47    | 61|   |
+   +   +   +---+---+   +---+   +   +
|  2|  5|   |       | 46    | 60  59|
+   +   +---+---+   +   +---+---+   +
|   |  6            | 45  44  43  58|
+---+   +---+---+---+---+---+   +---+
|      7|   |   | 37|       | 42    |
+---+   +   +   +   +   +---+   +---+
|  9   8  20  21| 36  35  40  41|   |
+   +---+   +   +---+   +---+---+   +
| 10| 24  23|   |     34|           |
+   +   +---+---+---+   +---+   +   +
| 11| 25  26  27    | 33|   |   |   |
+   +---+---+   +---+   +   +   +   +
| 13  12    | 28|   | 32    |   |   |
+   +   +   +   +   +   +   +   +---+
| 14|   |   | 29  30  31|          X|
+---+---+---+---+---+---+---+---+---+
```

| beat | to | dir | |
|---:|---|---|---|
| 1 | `r0100` | south | — |
| 2 | `r0000` | north | rejoins route, revisit, reversal |
| 3 | `r0001` | east | **on route** |
| 4 | `r0101` | south | **on route** |
| 5 | `r0201` | south | **on route** |
| 6 | `r0301` | south | **on route** |
| 7 | `r0401` | south | **on route** |
| 8 | `r0400` | west | — |
| 9 | `r0500` | south | — |
| 10 | `r0600` | south | — |
| 11 | `r0701` | ? | — |
| 12 | `r0700` | west | — |
| 13 | `r0800` | south | DEAD END |
| 14 | `r0700` | north | revisit, reversal |
| 15 | `r0600` | north | revisit |
| 16 | `r0500` | north | revisit |
| 17 | `r0400` | north | revisit |
| 18 | `r0401` | east | rejoins route, revisit |
| 19 | `r0402` | east | **on route** |
| 20 | `r0403` | east | — |
| 21 | `r0402` | west | rejoins route, revisit, reversal |
| 22 | `r0502` | south | **on route** |
| 23 | `r0501` | west | **on route** |
| 24 | `r0601` | south | **on route** |
| 25 | `r0602` | east | **on route** |
| 26 | `r0603` | east | **on route** |
| 27 | `r0703` | south | **on route** |
| 28 | `r0803` | south | **on route** |
| 29 | `r0804` | east | **on route** |
| 30 | `r0805` | east | **on route** |
| 31 | `r0705` | north | **on route** |
| 32 | `r0605` | north | — |
| 33 | `r0505` | north | — |
| 34 | `r0405` | north | — |
| 35 | `r0404` | west | — |
| 36 | `r0304` | north | DEAD END |
| 37 | `r0404` | south | revisit, reversal |
| 38 | `r0405` | east | revisit |
| 39 | `r0406` | east | — |
| 40 | `r0407` | east | — |
| 41 | `r0307` | north | — |
| 42 | `r0207` | north | — |
| 43 | `r0206` | west | — |
| 44 | `r0205` | west | — |
| 45 | `r0105` | north | — |
| 46 | `r0005` | north | — |
| 47 | `r0004` | west | — |
| 48 | `r0003` | west | — |
| 49 | `r0002` | west | — |
| 50 | `r0003` | east | revisit, reversal |
| 51 | `r0004` | east | revisit |
| 52 | `r0005` | east | revisit |
| 53 | `r0105` | south | revisit |
| 54 | `r0205` | south | revisit |
| 55 | `r0206` | east | revisit |
| 56 | `r0207` | east | revisit |
| 57 | `r0208` | east | — |
| 58 | `r0108` | north | — |
| 59 | `r0107` | west | — |
| 60 | `r0007` | north | DEAD END |


---

## Run 4 — did not arrive (59 moves, optimal 20)

`backtracks 27` · `reversals 5` · `idle 0` · `rooms seen 33/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   2|                   |   |   |
+   +   +   +---+---+   +---+   +   +
|   |  3|   |      8|       |       |
+   +   +---+---+   +   +---+---+   +
|   |  4   5   6   7|               |
+---+   +---+---+---+---+---+   +---+
|     12|   |   |   |       |       |
+---+   +   +   +   +   +---+   +---+
| 14  13  30  31|               |   |
+   +---+   +   +---+   +---+---+   +
| 15| 50  49|   |     60|           |
+   +   +---+---+---+   +---+   +   +
| 16| 51  52  53    | 59|   |   |   |
+   +---+---+   +---+   +   +   +   +
| 17  20  21| 54|   | 58    |   |   |
+   +   +   +   +   +   +   +   +---+
| 18| 41| 22| 55  56  57|          X|
+---+---+---+---+---+---+---+---+---+
```

| beat | to | dir | |
|---:|---|---|---|
| 1 | `r0001` | east | **on route** |
| 2 | `r0101` | south | **on route** |
| 3 | `r0201` | south | **on route** |
| 4 | `r0202` | east | — |
| 5 | `r0203` | east | — |
| 6 | `r0204` | east | — |
| 7 | `r0104` | north | — |
| 8 | `r0203` | ? | revisit |
| 9 | `r0202` | west | revisit |
| 10 | `r0201` | west | rejoins route, revisit |
| 11 | `r0301` | south | **on route** |
| 12 | `r0401` | south | **on route** |
| 13 | `r0400` | west | — |
| 14 | `r0500` | south | — |
| 15 | `r0600` | south | — |
| 16 | `r0700` | south | — |
| 17 | `r0800` | south | DEAD END |
| 18 | `r0700` | north | revisit, reversal |
| 19 | `r0701` | east | — |
| 20 | `r0702` | east | — |
| 21 | `r0802` | south | DEAD END |
| 22 | `r0702` | north | revisit, reversal |
| 23 | `r0701` | west | revisit |
| 24 | `r0700` | west | revisit |
| 25 | `r0600` | north | revisit |
| 26 | `r0500` | north | revisit |
| 27 | `r0400` | north | revisit |
| 28 | `r0401` | east | rejoins route, revisit |
| 29 | `r0402` | east | **on route** |
| 30 | `r0403` | east | — |
| 31 | `r0402` | west | rejoins route, revisit, reversal |
| 32 | `r0401` | west | rejoins route, revisit |
| 33 | `r0400` | west | revisit |
| 34 | `r0500` | south | revisit |
| 35 | `r0600` | south | revisit |
| 36 | `r0700` | south | revisit |
| 37 | `r0800` | south | revisit, DEAD END |
| 38 | `r0700` | north | revisit, reversal |
| 39 | `r0701` | east | revisit |
| 40 | `r0801` | south | DEAD END |
| 41 | `r0701` | north | revisit, reversal |
| 42 | `r0700` | west | revisit |
| 43 | `r0600` | north | revisit |
| 44 | `r0500` | north | revisit |
| 45 | `r0400` | north | revisit |
| 46 | `r0401` | east | rejoins route, revisit |
| 47 | `r0402` | east | **on route**, revisit |
| 48 | `r0502` | south | **on route** |
| 49 | `r0501` | west | **on route** |
| 50 | `r0601` | south | **on route** |
| 51 | `r0602` | east | **on route** |
| 52 | `r0603` | east | **on route** |
| 53 | `r0703` | south | **on route** |
| 54 | `r0803` | south | **on route** |
| 55 | `r0804` | east | **on route** |
| 56 | `r0805` | east | **on route** |
| 57 | `r0705` | north | **on route** |
| 58 | `r0605` | north | — |
| 59 | `r0505` | north | — |


---

## Run 5 — reached the goal (20 moves, optimal 20)

`backtracks 0` · `reversals 0` · `idle 0` · `rooms seen 21/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   2|                   |   |   |
+   +   +   +---+---+   +---+   +   +
|   |  3|   |       |       |       |
+   +   +---+---+   +   +---+---+   +
|   |  4            |               |
+---+   +---+---+---+---+---+   +---+
|      5|   |   |   |       |       |
+---+   +   +   +   +   +---+   +---+
|      6   7    |               |   |
+   +---+   +   +---+   +---+---+   +
|   |  9   8|   |       |           |
+   +   +---+---+---+   +---+   +   +
|   | 10  11  12    |   |   |   |   |
+   +---+---+   +---+   +   +   +   +
|           | 13|   | 17  18|   |   |
+   +   +   +   +   +   +   +   +---+
|   |   |   | 14  15  16| 19  20  21|
+---+---+---+---+---+---+---+---+---+
```

| beat | to | dir | |
|---:|---|---|---|
| 1 | `r0001` | east | **on route** |
| 2 | `r0101` | south | **on route** |
| 3 | `r0201` | south | **on route** |
| 4 | `r0301` | south | **on route** |
| 5 | `r0401` | south | **on route** |
| 6 | `r0402` | east | **on route** |
| 7 | `r0502` | south | **on route** |
| 8 | `r0501` | west | **on route** |
| 9 | `r0601` | south | **on route** |
| 10 | `r0602` | east | **on route** |
| 11 | `r0603` | east | **on route** |
| 12 | `r0703` | south | **on route** |
| 13 | `r0803` | south | **on route** |
| 14 | `r0804` | east | **on route** |
| 15 | `r0805` | east | **on route** |
| 16 | `r0705` | north | **on route** |
| 17 | `r0706` | east | **on route** |
| 18 | `r0806` | south | **on route** |
| 19 | `r0807` | east | **on route** |
| 20 | `r0808` | east | **on route**, DEAD END |
