(function registerFixture() {
  if (!window.Sonder) return;

  const state = Sonder.state();
  Sonder.registerSidebarTab({
    id: "fixture-sidebar",
    label: state.chat ? state.chat.name : "Fixture",
    render(container) {
      container.textContent = "Fixture sidebar";
    },
  });
  Sonder.registerTopBarButton({
    id: "fixture-action",
    icon: "F",
    title: "Fixture action",
    onClick() {
      return Sonder.api("GET", "/api/fixture-ping");
    },
  });
  Sonder.registerView({
    id: "fixture-view",
    label: "Fixture view",
    render(container) {
      container.textContent = "Fixture view mounted";
    },
  });
  Sonder.registerComposerControl({
    id: "fixture-composer",
    render(container) {
      container.textContent = "Fixture composer";
    },
  });
  Sonder.registerSettingsSection({
    id: "fixture-settings",
    label: "Fixture settings",
    render(container) {
      container.textContent = "Fixture settings";
    },
  });
  Sonder.registerStepRenderer("ext:fixture-v1:step", (content, container) => {
    container.textContent = String(content?.value || "");
  });
  Sonder.notify({
    title: "Fixture ready",
    body: "The v1 fixture registered.",
    level: "ok",
  });
  Sonder.on("turn:done", payload => (
    Sonder.call("fixture-v1", "POST", "/x/seen", payload)
  ));
  Sonder.chats.list();
})();
