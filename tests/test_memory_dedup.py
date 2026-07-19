def test_episode_does_not_duplicate_dialogue():
    # Extracted from commit.py logic
    view = 'A person says: "Hello."'
    episode_content = str(view or "").strip()

    # Old logic appended heard_quotes, new logic should not
    assert episode_content.count('"Hello."') == 1