"""Real-browser proof for lossless reusable-person editing."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


def test_character_editor_preserves_unknown_fields_through_advanced_json(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const editorModule = await import(
            `${base}/static/js/ui-next/library-editors/character-persona.js?release=wp07.1`
          );
          const original = {
            identity: { uid: "char-a", name: "Asha", aliases: ["Ash"],
              pronouns: { subject: "she", object: "her", possessive: "her" } },
            embodiment: { visible: { summary: "Copper hair" } },
            knowledge: { public_history: "Archive keeper" },
            opening: { first_message: "Welcome." },
            extension_payload: { nested: [1, { exact: true }] },
          };
          let staged = null;
          const services = {
            localizer: { t: value => value },
            authoring: { stage: value => { staged = structuredClone(value); } },
          };
          const host = document.createElement("div");
          document.body.append(host);
          host.append(editorModule.createPersonEditor({
            document, services,
            state: { kind: "character", id: 4, status: "saved",
              draft: structuredClone(original) },
          }));
          const name = host.querySelector('[name="identity.name"]');
          name.value = "Asha Vale";
          name.dispatchEvent(new Event("input", { bubbles: true }));
          const afterForm = structuredClone(staged);
          const advanced = host.querySelector('[name="advanced_json"]');
          const parsed = JSON.parse(advanced.value);
          parsed.extension_payload.nested[1].exact = "still here";
          advanced.value = JSON.stringify(parsed, null, 2);
          host.querySelector('[data-apply-advanced]').click();
          const afterAdvanced = structuredClone(staged);
          host.remove();
          return { afterForm, afterAdvanced };
        }""",
        ui_base_url,
    )
    assert result["afterForm"]["identity"]["name"] == "Asha Vale"
    assert result["afterForm"]["extension_payload"] == {
        "nested": [1, {"exact": True}],
    }
    assert result["afterAdvanced"]["extension_payload"] == {
        "nested": [1, {"exact": "still here"}],
    }
