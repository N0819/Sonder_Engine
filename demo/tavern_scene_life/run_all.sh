#!/usr/bin/env bash
# Re-seed and play the tavern scene-life test end to end.
set -u
cd /home/nathan/Documents/Fiction-improved/Fiction/.claude/worktrees/background-life-design
D=demo/tavern_scene_life
rm -f $D/run_log.jsonl
python3 $D/seed.py || exit 1

play () {
  timeout 1200 python3 -u $D/play_turn.py "$1" 2>&1 \
    | grep -vE --line-buffered '"level": "INFO"'
}

play ""
play "We shoulder through to the bar. Bran drops his good hand flat on the plank. 'Three ales, and a room if you've got one.'"
play "Ysolde plants her elbows on the bar beside Bran. 'Before you pour — what do people hereabouts say about the barrow out on the moor?'"
play "Bran squints at the price. 'Two silver for a room with no fire in it? That's a town price. We'll pay one and a half and you'll still be ahead.'"
play "I let Bran argue and turn my back to the bar, watching the room while the two of them go at it."
play "Ysolde drifts off toward the old woman by the hearth and crouches down beside her. 'You've lived here a while, haven't you.'"
play "Bran thumps his empty tankard down and announces to nobody in particular that the barrow's been robbed twice already and there's nothing left in it worth the walk."
echo "@@@ DONE @@@"
