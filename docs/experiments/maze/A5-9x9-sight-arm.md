# The maze runs, move by move

Actual movements from the sight arm — the configuration that reached the goal. Same maze, same seed, same models for all five runs; only the character's accumulated memory differs.

Numbers in each grid are the beat a room was **first** entered. `*` marks the optimal route where he never went, `X` the shrine.

## The maze

9×9 Kruskal, 81 rooms, 21 junctions, 25 dead ends, optimal **20 moves**.

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

## Run 1 — reached the shrine (28 moves, optimal 20)

`backtracks 7` · `reversals 6` · `idle 0` · `rooms seen 22/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   2|                   |   |   |
+   +   +   +---+---+   +---+   +   +
|   |  7|   |       |       |       |
+   +   +---+---+   +   +---+---+   +
|   |  8            |               |
+---+   +---+---+---+---+---+   +---+
|      9|   |   |   |       |       |
+---+   +   +   +   +   +---+   +---+
|     10  11  12|               |   |
+   +---+   +   +---+   +---+---+   +
|   | 17  16|   |       |           |
+   +   +---+---+---+   +---+   +   +
|   | 18  19  20    |   |   |   |   |
+   +---+---+   +---+   +   +   +   +
|           | 21|   | 25  26|   |   |
+   +   +   +   +   +   +   +   +---+
|   |   |   | 22  23  24| 27  28  29|
+---+---+---+---+---+---+---+---+---+
```

| beat | to | dir | |
|---:|---|---|---|
| 1 | `r0001` | east | **on route** |
| 2 | `r0000` | west | rejoins route, revisit, reversal |
| 3 | `r0001` | east | **on route**, revisit, reversal |
| 4 | `r0000` | west | rejoins route, revisit, reversal |
| 5 | `r0001` | east | **on route**, revisit, reversal |
| 6 | `r0101` | south | **on route** |
| 7 | `r0201` | south | **on route** |
| 8 | `r0301` | south | **on route** |
| 9 | `r0401` | south | **on route** |
| 10 | `r0402` | east | **on route** |
| 11 | `r0403` | east | — |
| 12 | `r0402` | west | rejoins route, revisit, reversal |
| 13 | `r0401` | west | rejoins route, revisit |
| 14 | `r0402` | east | **on route**, revisit, reversal |
| 15 | `r0502` | south | **on route** |
| 16 | `r0501` | west | **on route** |
| 17 | `r0601` | south | **on route** |
| 18 | `r0602` | east | **on route** |
| 19 | `r0603` | east | **on route** |
| 20 | `r0703` | south | **on route** |
| 21 | `r0803` | south | **on route** |
| 22 | `r0804` | east | **on route** |
| 23 | `r0805` | east | **on route** |
| 24 | `r0705` | north | **on route** |
| 25 | `r0706` | east | **on route** |
| 26 | `r0806` | south | **on route** |
| 27 | `r0807` | east | **on route** |
| 28 | `r0808` | east | **on route**, DEAD END |


---

## Run 2 — reached the shrine (20 moves, optimal 20)

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


---

## Run 3 — did not arrive (56 moves, optimal 20)

`backtracks 41` · `reversals 12` · `idle 4` · `rooms seen 20/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   2|                   |   |   |
+   +   +   +---+---+   +---+   +   +
|   |  3|   |     16|       |       |
+   +   +---+---+   +   +---+---+   +
|   |  4  13  14  15|               |
+---+   +---+---+---+---+---+   +---+
|      5|   |   |   |       |       |
+---+   +   +   +   +   +---+   +---+
| 29   6   7  26|               |   |
+   +---+   +   +---+   +---+---+   +
| 30|      8|   |       |           |
+   +   +---+---+---+   +---+   +   +
| 31|               |   |   |   |   |
+   +---+---+   +---+   +   +   +   +
| 32  33  34|   |   |       |   |   |
+   +   +   +   +   +   +   +   +---+
| 41|   |   |           |          X|
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
| 8 | `r0402` | north | rejoins route, revisit, reversal |
| 9 | `r0401` | west | rejoins route, revisit |
| 10 | `r0301` | north | rejoins route, revisit |
| 11 | `r0201` | north | rejoins route, revisit |
| 12 | `r0202` | east | — |
| 13 | `r0203` | east | — |
| 14 | `r0204` | east | — |
| 15 | `r0104` | north | — |
| 16 | `r0204` | south | revisit, reversal |
| 17 | `r0203` | west | revisit |
| 18 | `r0203` | — | stayed put |
| 19 | `r0203` | — | stayed put |
| 20 | `r0202` | west | revisit |
| 21 | `r0201` | west | rejoins route, revisit |
| 22 | `r0301` | south | **on route**, revisit |
| 23 | `r0401` | south | **on route**, revisit |
| 24 | `r0402` | east | **on route**, revisit |
| 25 | `r0403` | east | — |
| 26 | `r0402` | west | rejoins route, revisit, reversal |
| 27 | `r0401` | west | rejoins route, revisit |
| 28 | `r0400` | west | — |
| 29 | `r0500` | south | — |
| 30 | `r0600` | south | — |
| 31 | `r0700` | south | — |
| 32 | `r0701` | east | — |
| 33 | `r0702` | east | — |
| 34 | `r0701` | west | revisit, reversal |
| 35 | `r0700` | west | revisit |
| 36 | `r0701` | east | revisit, reversal |
| 37 | `r0700` | west | revisit, reversal |
| 38 | `r0701` | east | revisit, reversal |
| 39 | `r0700` | west | revisit, reversal |
| 40 | `r0800` | south | DEAD END |
| 41 | `r0700` | north | revisit, reversal |
| 42 | `r0701` | east | revisit |
| 43 | `r0700` | west | revisit, reversal |
| 44 | `r0700` | — | stayed put |
| 45 | `r0600` | north | revisit |
| 46 | `r0500` | north | revisit |
| 47 | `r0400` | north | revisit |
| 48 | `r0401` | east | rejoins route, revisit |
| 49 | `r0402` | east | **on route**, revisit |
| 50 | `r0403` | east | revisit |
| 51 | `r0402` | west | rejoins route, revisit, reversal |
| 52 | `r0401` | west | rejoins route, revisit |
| 53 | `r0400` | west | revisit |
| 54 | `r0400` | — | stayed put |
| 55 | `r0500` | south | revisit |
| 56 | `r0600` | south | revisit |
| 57 | `r0700` | south | revisit |
| 58 | `r0701` | east | revisit |
| 59 | `r0702` | east | revisit |
| 60 | `r0701` | west | revisit, reversal |


---

## Run 4 — did not arrive (52 moves, optimal 20)

`backtracks 26` · `reversals 2` · `idle 8` · `rooms seen 35/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   2| 44  43  42  41    |   |   |
+   +   +   +---+---+   +---+   +   +
|   |  3| 45|       | 40    | 27  26|
+   +   +---+---+   +   +---+---+   +
|   |  4            | 36  35  24  25|
+---+   +---+---+---+---+---+   +---+
|      5|   |   |   |       | 23    |
+---+   +   +   +   +   +---+   +---+
|      6   7    |     20  21  22|   |
+   +---+   +   +---+   +---+---+   +
|   |  9   8|   |     19|           |
+   +   +---+---+---+   +---+   +   +
|   | 10  11  12    | 18|   |   |   |
+   +---+---+   +---+   +   +   +   +
|           | 13|   | 17    |   |   |
+   +   +   +   +   +   +   +   +---+
|   |   |   | 14  15  16|          X|
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
| 17 | `r0605` | north | — |
| 18 | `r0505` | north | — |
| 19 | `r0405` | north | — |
| 20 | `r0406` | east | — |
| 21 | `r0407` | east | — |
| 22 | `r0307` | north | — |
| 23 | `r0207` | north | — |
| 24 | `r0208` | east | — |
| 25 | `r0108` | north | — |
| 26 | `r0107` | west | — |
| 27 | `r0107` | — | stayed put |
| 28 | `r0108` | east | revisit |
| 29 | `r0208` | south | revisit |
| 30 | `r0208` | — | stayed put |
| 31 | `r0208` | — | stayed put |
| 32 | `r0208` | — | stayed put |
| 33 | `r0207` | west | revisit |
| 34 | `r0206` | west | — |
| 35 | `r0205` | west | — |
| 36 | `r0205` | — | stayed put |
| 37 | `r0205` | — | stayed put |
| 38 | `r0205` | — | stayed put |
| 39 | `r0105` | north | — |
| 40 | `r0005` | north | — |
| 41 | `r0004` | west | — |
| 42 | `r0003` | west | — |
| 43 | `r0002` | west | — |
| 44 | `r0102` | south | DEAD END |
| 45 | `r0102` | — | stayed put |
| 46 | `r0002` | north | revisit |
| 47 | `r0003` | east | revisit |
| 48 | `r0004` | east | revisit |
| 49 | `r0005` | east | revisit |
| 50 | `r0105` | south | revisit |
| 51 | `r0205` | south | revisit |
| 52 | `r0206` | east | revisit |
| 53 | `r0207` | east | revisit |
| 54 | `r0208` | east | revisit |
| 55 | `r0108` | north | revisit |
| 56 | `r0208` | south | revisit, reversal |
| 57 | `r0207` | west | revisit |
| 58 | `r0206` | west | revisit |
| 59 | `r0205` | west | revisit |
| 60 | `r0206` | east | revisit, reversal |


---

## Run 5 — did not arrive (59 moves, optimal 20)

`backtracks 24` · `reversals 6` · `idle 1` · `rooms seen 37/81`

```
+---+---+---+---+---+---+---+---+---+
|  1   4| 40  39  38  37    |   |   |
+   +   +   +---+---+   +---+   +   +
|  2|  5|   |       | 36    |     30|
+   +   +---+---+   +   +---+---+   +
|   |  6            | 35  34  28  29|
+---+   +---+---+---+---+---+   +---+
|      7|   |   |   |       | 27    |
+---+   +   +   +   +   +---+   +---+
|      8   9    | 52  24  25  26|   |
+   +---+   +   +---+   +---+---+   +
|   | 11  10|   |     23|           |
+   +   +---+---+---+   +---+   +   +
|   | 12  13  14  15| 22|   |   |   |
+   +---+---+   +---+   +   +   +   +
|           | 17| 61| 21    |   |   |
+   +   +   +   +   +   +   +   +---+
|   |   |   | 18  19  20|          X|
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
| 8 | `r0402` | east | **on route** |
| 9 | `r0502` | south | **on route** |
| 10 | `r0501` | west | **on route** |
| 11 | `r0601` | south | **on route** |
| 12 | `r0602` | east | **on route** |
| 13 | `r0603` | east | **on route** |
| 14 | `r0604` | east | DEAD END |
| 15 | `r0603` | west | rejoins route, revisit, reversal |
| 16 | `r0703` | south | **on route** |
| 17 | `r0803` | south | **on route** |
| 18 | `r0804` | east | **on route** |
| 19 | `r0805` | east | **on route** |
| 20 | `r0705` | north | **on route** |
| 21 | `r0605` | north | — |
| 22 | `r0505` | north | — |
| 23 | `r0405` | north | — |
| 24 | `r0406` | east | — |
| 25 | `r0407` | east | — |
| 26 | `r0307` | north | — |
| 27 | `r0207` | north | — |
| 28 | `r0208` | east | — |
| 29 | `r0108` | north | — |
| 30 | `r0208` | south | revisit, reversal |
| 31 | `r0208` | — | stayed put |
| 32 | `r0207` | west | revisit |
| 33 | `r0206` | west | — |
| 34 | `r0205` | west | — |
| 35 | `r0105` | north | — |
| 36 | `r0005` | north | — |
| 37 | `r0004` | west | — |
| 38 | `r0003` | west | — |
| 39 | `r0002` | west | — |
| 40 | `r0003` | east | revisit, reversal |
| 41 | `r0004` | east | revisit |
| 42 | `r0005` | east | revisit |
| 43 | `r0105` | south | revisit |
| 44 | `r0205` | south | revisit |
| 45 | `r0206` | east | revisit |
| 46 | `r0207` | east | revisit |
| 47 | `r0307` | south | revisit |
| 48 | `r0407` | south | revisit |
| 49 | `r0406` | west | revisit |
| 50 | `r0405` | west | revisit |
| 51 | `r0404` | west | — |
| 52 | `r0405` | east | revisit, reversal |
| 53 | `r0505` | south | revisit |
| 54 | `r0605` | south | revisit |
| 55 | `r0705` | south | rejoins route, revisit |
| 56 | `r0805` | south | rejoins route, revisit |
| 57 | `r0804` | west | rejoins route, revisit |
| 58 | `r0803` | west | rejoins route, revisit |
| 59 | `r0804` | east | **on route**, revisit, reversal |
| 60 | `r0704` | north | DEAD END |

