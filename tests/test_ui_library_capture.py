from tools.capture_ui_library import apply_action


class _Role:
    def __init__(self, page, name, scope="page"):
        self.page = page
        self.name = name
        self.scope = scope

    def get_by_text(self, name, *, exact):
        assert exact is True
        return _Role(self.page, name, self.name)

    def get_by_role(self, role, *, name):
        assert role == "button"
        return _Role(self.page, name, self.name)

    def click(self):
        self.page.events.append(("click", self.scope, self.name))

    def wait_for(self):
        self.page.events.append(("wait_for", self.name))


class _Page:
    def __init__(self):
        self.events = []

    def get_by_role(self, role, *, name):
        assert (role, name) in {
            ("complementary", "Library details"),
            ("button", "Undo"),
        }
        return _Role(self, name)

    def wait_for_function(self, expression):
        self.events.append(("wait_for_function", expression))


def test_restore_capture_opens_character_more_menu_before_restore():
    page = _Page()

    apply_action(page, "restore")

    assert page.events[:2] == [
        ("click", "Library details", "More"),
        ("click", "Library details", "Restore character"),
    ]
