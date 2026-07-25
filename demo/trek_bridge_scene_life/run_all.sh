#!/usr/bin/env bash
# Enterprise-D bridge: Picard is the only real character, the crew are
# background presences, the player is a near-silent observation officer.
set -u
cd /home/nathan/Documents/Fiction-improved/Fiction/.claude/worktrees/background-life-design
D=demo/trek_bridge_scene_life
rm -f $D/run_log.jsonl
python3 $D/seed.py || exit 1

play () {
  timeout 1200 python3 -u $D/play_turn.py "$1" 2>&1 \
    | grep -vE --line-buffered '"level": "INFO"'
}

play ""
play "I take the aft rail station, key my PADD, and log the start time. 'Whenever you're ready, Captain. I'm recording procedure, not performance.'"
play "I watch the bridge instead of the viewscreen, noting who looks at whom before they speak."
play "The simulation escalates without warning: two Romulan warbirds decloak off the port bow, weapons charged, and the drill clock keeps running."
play "I say nothing and keep writing."
play "The exercise feeds a casualty into the drill — tactical's console shorts out and the station goes dark mid-engagement."
play "'Captain — for the record. That last call came from the deck, not the chair. Was that intended?'"
echo "@@@ DONE @@@"
