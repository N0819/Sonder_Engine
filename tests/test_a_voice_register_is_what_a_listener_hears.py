"""A card's voice register is what a listener hears, not how to write the lines.

Found in play on 2026-10-06 (scratch story 165, turn 4579). The composer says a
speaker's `social.voice.register` once to each observer as the voice's own
manner (D2, `composer.speech_percept`), and the engine's card generator had
filled Hester Gale's with writing directions: "Low, plain-spoken, fen
working-class. No flourish. Sentences are short and load-bearing." Her first
line reached the player's view as "The voice is low, plain-spoken, fen
working-class. No flourish. Sentences are short and load-bearing.", and the
narrator set it on the page mid-dialogue as prose.

No authoring prompt said what the field was for -- the generator's schema
gives it as `"register": ""` -- so the rule lives in the fragment every card
surface embeds (`card_person_note`, beside the paragraph that already names
`social.voice` as read by everyone who is not the character).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "language_packs"


def test_both_packs_say_the_register_is_heard_and_the_phrasing_is_not():
    for lang in ("en", "ja"):
        text = (ROOT / lang / "cards/system_prompts/card_person_note.txt"
                ).read_text(encoding="utf-8")
        paragraph = next(p for p in text.split("\n")
                         if "`social.voice.register`" in p)
        assert "`cadence`" in paragraph and "`notes`" in paragraph, lang
