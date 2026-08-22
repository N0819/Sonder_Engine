# 21. Motion, Sound, and Feedback

## Motion principle

Motion should explain cause, continuity, or state. It should not exist merely to make the interface feel technological.

## Motion categories

### Structural transitions

Used for:

- opening/closing inspector;
- destination change;
- dialog/sheet appearance;
- list-to-detail transition on mobile;
- expanding a section.

Duration guidance: approximately 120-220 ms with restrained easing.

### Content transitions

Used for:

- new turn appearance;
- backdrop dissolve;
- status change;
- save confirmation.

Content motion must not shift reading position unexpectedly.

### Ambient effects

Weather, hearth, backdrop movement, or other continuous effects are optional atmosphere. They must respect effects settings, reduced motion, tab visibility, and power constraints.

## Prohibited motion

- pulsing borders at rest;
- continuous scanning lines;
- animated noise/grain;
- repeated glow cycles;
- motion on every hover;
- large panel bounce;
- decorative parallax that competes with prose;
- layout movement caused by border-width changes.

## Feedback hierarchy

### Immediate interaction

Hover, pressed, selected, and focus states respond within the control.

### Short result

Use inline status or a toast for quick success/failure.

### Long task

Use background activity with task name, progress or elapsed time, cancelability, and completion result.

### Persistent problem

Use an inline notice or status panel, not a transient toast alone.

## Save feedback

Long-form editors should show:

- Saving...
- Saved
- Could not save

The indicator should remain in a stable location and not cause layout shift.

## Sound

Sonder may use sound for:

- ambience selected by the story;
- optional completion chime;
- explicit preview actions.

Application interaction sounds are off by default unless separately approved. The interface must not become noisy or game-like.

## Ambience controls

Ambience uses an Instrument Cluster or compact contextual panel. Mute remains immediately available. Reroll/change and detailed settings may be one level deeper on mobile.

## Reduced effects

Effects levels:

- **Full**: approved atmosphere and transitions.
- **Reduced**: visual layers remain where useful, but continuous movement and most transitions stop.
- **Off**: decorative overlays are not drawn; content backdrops may remain static.

Reduced motion from the operating system should apply before first paint and map to Reduced unless the user has explicitly chosen a stronger preference.

## Performance

- Avoid permanent full-viewport compositing when the page is hidden.
- Disable blur behind animated weather where necessary.
- Prefer transform/opacity for short transitions.
- Avoid unbounded animation loops.
- Motion must not reduce composer responsiveness or transcript scrolling.
