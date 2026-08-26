# 21. Motion, Sound, and Feedback

## Motion principle

The workbench is static at rest. Motion explains structure, direct
manipulation, or state change. It does not simulate electronic activity.

## Canonical timing

| Motion | Duration | Purpose |
|---|---:|---|
| Hover/focus material response | 120 ms | local control feedback |
| Tab reorder preview | 150 ms | reveal resulting order |
| Module/shelf rearrangement | 180-190 ms | preserve spatial continuity |
| Toolbar open/close | 260 ms | reveal/collapse dock |
| Backdrop/canvas change | 260-500 ms | nonblocking atmospheric continuity |

Use restrained cubic-bezier easing. Dragged objects follow the pointer directly
and do not ease behind it.

## Docking feedback

- Title/tab target: highlight bar, show insertion caret, shift tabs live.
- Shelf target: reveal broad horizontal rail and exact ghost outline.
- Float: dragged module itself remains the preview.
- Widget Shelf: explicit return target highlights.
- Invalid: show no false positive; release restores origin.

Target state must not flicker between tab and shelf across a one-pixel boundary.
Use stable target ownership and generous hit regions.

## Prohibited motion

- material activity loops;
- animated grain/noise;
- CRT sparkle or pixel crawl;
- scanlines;
- pulsing borders at rest;
- repeated glow breathing;
- a trailing float ghost;
- bounce or springy dashboard motion;
- border-width layout shift.

## Activity and progress

Generation, saving, connection, and background work use concise text, status
markers, progress/elapsed state where useful, and Stop/Cancel when supported.
Do not turn operation state into ambient sparkling material.

## Reduced motion

Reduced motion removes rearrangement interpolation, toolbar translation,
backdrop dissolves, and decorative canvas movement. Direct manipulation still
updates position and target instantly. State remains understandable without
transition.

## Sound

Story ambience and explicit previews are content. Optional completion chimes
may exist. Generic UI clicks and electronic bleeps are off by default and are
not part of the signature style.
