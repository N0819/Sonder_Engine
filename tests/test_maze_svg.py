"""The authored-maze path: an SVG file IS the maze.

A seeded maze is only reproducible for as long as nobody touches the carver or
the RNG. An arm run against `tools/mazes/*.svg` stays reproducible because the
walls are the file, so these tests pin the parse of the checked-in fixture --
if the parser drifts, an old arm's routes would render against different walls
and every derived annotation would be fiction.

Database-independent by construction: no pipeline, no engine, just geometry.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools.maze_experiment as M

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "tools", "mazes", "maze7x7-a11.svg")


@pytest.fixture(scope="module")
def parsed():
    return M.maze_from_svg(FIXTURE)


def test_it_reads_the_grid_and_the_doors(parsed):
    walls, grid, start, goal = parsed
    assert grid == 7
    assert len(walls) == 49
    # Start and goal come from the border gaps, NOT from (0,0)/(n-1,n-1).
    # Getting this wrong puts the character in a room the maze does not open
    # from, which reads as a navigation failure rather than a harness bug.
    assert start == (0, 3)
    assert goal == (6, 3)


def test_it_is_a_perfect_maze_and_solvable(parsed):
    walls, grid, start, goal = parsed
    st = M.maze_stats(walls, grid)
    assert st["edges"] == 48 and st["loops"] == 0
    assert st["dead_ends"] == 6 and st["junctions"] == 4
    path = M.shortest_path(walls, start, goal)
    assert path[0] == start and path[-1] == goal
    assert len(path) - 1 == 28


def test_every_room_is_reachable(parsed):
    """An unreachable room is a room the character can never learn. Silent, and
    it would show up only as an unexplained ceiling on coverage."""
    walls, grid, start, _ = parsed
    seen, stack = {start}, [start]
    while stack:
        for n in walls[stack.pop()]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    assert len(seen) == grid * grid


def test_adjacency_is_symmetric(parsed):
    """`b in walls[a]` must imply `a in walls[b]`. A one-way edge would let the
    character walk into a room whose exits do not include the one behind
    them -- a false dead end, indistinguishable from the real thing."""
    walls, _, _, _ = parsed
    for cell, ns in walls.items():
        for n in ns:
            assert cell in walls[n], f"{cell}->{n} is one-way"


def test_it_is_deceptive_enough_to_measure_learning(parsed):
    """The point of choosing this maze: it is small but has real traps. A maze
    whose wrong turns are all one room deep cannot distinguish a character who
    learned the route from one who guesses and recovers cheaply."""
    walls, grid, start, goal = parsed
    dec = M.deception_stats(walls, start, goal)
    assert dec["off_path"] >= 15
    assert dec["max_depth"] >= 5
    assert dec["deep_traps"] >= 2


def test_fingerprint_tracks_shape_not_size(parsed):
    """Resume refuses across mazes on this value, so it must change when the
    walls change and not merely when the grid does."""
    walls, grid, start, goal = parsed
    fp = M.maze_fingerprint(walls, start, goal)
    assert fp == M.maze_fingerprint(dict(walls), start, goal)

    moved = {c: set(ns) for c, ns in walls.items()}
    a, b = (0, 0), (0, 1)
    moved[a].discard(b)
    moved[b].discard(a)
    assert M.maze_fingerprint(moved, start, goal) != fp
    assert M.maze_fingerprint(walls, start, (5, 3)) != fp


def test_bad_svgs_fail_loudly(tmp_path):
    """Every one of these silently produced a plausible-looking maze at some
    point in development. A wrong maze that runs is worse than no maze."""
    def svg(body):
        p = tmp_path / "m.svg"
        p.write_text('<svg xmlns="http://www.w3.org/2000/svg">%s</svg>' % body)
        return str(p)

    with pytest.raises(SystemExit, match="no <line>"):
        M.maze_from_svg(svg('<rect x="0" y="0" width="10" height="10"/>'))

    with pytest.raises(SystemExit, match="diagonal"):
        M.maze_from_svg(svg('<line x1="0" y1="0" x2="16" y2="16"/>'
                            '<line x1="0" y1="0" x2="0" y2="32"/>'))

    # A sealed 2x2: no entrance, no exit, nowhere to infer start and goal.
    # Interior walls included because cell size is inferred from coordinate
    # spacing -- a bare box has only two distinct coordinates and parses as a
    # single cell.
    box = "".join(
        '<line x1="%d" y1="%d" x2="%d" y2="%d"/>' % s for s in (
            (0, 0, 32, 0), (0, 32, 32, 32), (0, 0, 0, 32), (32, 0, 32, 32),
            (0, 16, 32, 16), (16, 0, 16, 32)))
    with pytest.raises(SystemExit, match="openings in the outer border"):
        M.maze_from_svg(svg(box))

    # Walled-off exit: parses, looks like a maze, and is unwinnable. The
    # character would run the full step budget every time and the arm would
    # read as a total learning failure.
    # Entrance over cell (0,0), exit under cell (1,1), every interior wall
    # present -- two doors, four isolated rooms.
    sealed = "".join(
        '<line x1="%d" y1="%d" x2="%d" y2="%d"/>' % s for s in (
            (16, 0, 32, 0), (0, 32, 16, 32), (0, 0, 0, 32), (32, 0, 32, 32),
            (0, 16, 32, 16), (16, 0, 16, 32)))
    with pytest.raises(SystemExit, match="walled off"):
        M.maze_from_svg(svg(sealed))


def test_renderer_rebuilds_from_recorded_edges(parsed):
    """The results file carries its own walls. Rebuilding from seed+algo was
    only ever a proxy, and there is no recipe at all for an authored maze."""
    from tools.render_maze_runs import Maze
    walls, grid, start, goal = parsed
    meta = {"grid": grid, "start": list(start), "goal": list(goal),
            "edges": sorted({(min(a, b), max(a, b))
                             for a, ns in walls.items() for b in ns})}
    mz = Maze(meta)
    assert mz.walls == walls
    assert len(mz.opt) - 1 == 28
