export const MODULE_RELEASE = "alpha98-ui11-0acc47fb0573";

import { button, element, errorState, markData, replaceLocalized, stateMessage, toolScope } from "./shared.js?release=alpha98-ui11-0acc47fb0573";

// UI_CATALOG_START: Multiplayer tool copy.
const COPY = Object.freeze({
  loading: "Loading story participants…",
  empty: "No additional players are attached.",
  add: "Attach player",
  invite: "Create invite",
  revoke: "Revoke invite",
  detach: "Detach player",
  confirmDetach: "Confirm detach",
  cancel: "Cancel",
  pending: "Invite pending",
  active: "Guest connected",
  share: "Share this one-time join link now. It is not saved in this browser.",
  copied: "Invite link copied.",
});
// UI_CATALOG_END

export function mountMultiplayerTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "multiplayer");
  let stopped = false;
  let revealedInvite = null;
  let confirmingPersona = null;

  const load = async () => {
    const { chatId } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const [personaData, grantData] = await Promise.all([
        scope.run("GET", "personas", `/api/chats/${chatId}/personas`),
        scope.run("GET", "invites", `/api/chats/${chatId}/guest_invites`),
      ]);
      if (stopped || !scope.isLive() || !personaData || !grantData) return;
      render(personaData.personas || [], grantData.grants || []);
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message, load));
    }
  };

  const save = async (method, key, path, body, onSuccess = null) => {
    try {
      const data = await scope.run(method, key, path, body);
      onSuccess?.(data);
      await load();
    } catch (error) {
      target.prepend(stateMessage(documentRef, errorState(error).state, errorState(error).message, load));
      services.localizer.localize(target);
    }
  };

  const render = (personas, grants) => {
    const { chatId } = scope.current();
    const body = element(documentRef, "div", "ui-tool-stack ui-multiplayer");
    if (revealedInvite) {
      const reveal = element(documentRef, "section", "ui-tool-card ui-invite-result");
      reveal.setAttribute("aria-live", "polite");
      reveal.append(element(documentRef, "p", "", COPY.share));
      const output = element(documentRef, "output", "ui-invite-result__link", revealedInvite.link);
      markData(output);
      output.dataset.inviteSecret = "ephemeral";
      const copy = button(documentRef, "Copy invite link", "ui-button ui-button--primary");
      copy.addEventListener("click", async () => {
        await navigator.clipboard?.writeText(revealedInvite.link);
        copy.textContent = services.localizer.t(COPY.copied);
      });
      reveal.append(output, copy);
      body.append(reveal);
    }
    if (!personas.length) body.append(stateMessage(documentRef, "empty", COPY.empty));
    for (const persona of personas) {
      const card = element(documentRef, "article", "ui-tool-card");
      const head = element(documentRef, "header", "ui-tool-card__header");
      head.append(markData(element(documentRef, "h4", "ui-heading ui-heading--5", persona.name)));
      const grant = grants.find(item => Number(item.persona_id) === Number(persona.id)
        && ["pending", "active"].includes(item.status));
      if (grant) {
        head.append(element(documentRef, "span", "ui-badge", grant.status === "active" ? COPY.active : COPY.pending));
        const revoke = button(documentRef, COPY.revoke);
        revoke.addEventListener("click", () => save("DELETE", `revoke-${grant.id}`, `/api/chats/${chatId}/guest_invites/${grant.id}`));
        head.append(revoke);
      } else {
        const inviteControl = button(documentRef, COPY.invite, "ui-button ui-button--primary");
        inviteControl.addEventListener("click", () => save(
          "POST", `invite-${persona.id}`, `/api/chats/${chatId}/guest_invites`,
          { persona_id: persona.id },
          invite => {
            if (!invite?.code) return;
            revealedInvite = {
              grantId: invite.grant_id,
              link: `${location.origin}/guest?code=${encodeURIComponent(invite.code)}`,
            };
          },
        ));
        head.append(inviteControl);
      }
      const detach = button(documentRef,
        confirmingPersona === persona.id ? COPY.confirmDetach : COPY.detach);
      detach.addEventListener("click", () => {
        if (confirmingPersona !== persona.id) {
          confirmingPersona = persona.id;
          render(personas, grants);
          return;
        }
        revealedInvite = null;
        confirmingPersona = null;
        save("DELETE", `detach-${persona.id}`, `/api/chats/${chatId}/personas/${persona.id}`);
      });
      head.append(detach);
      if (confirmingPersona === persona.id) {
        const cancel = button(documentRef, COPY.cancel);
        cancel.addEventListener("click", () => {
          confirmingPersona = null;
          render(personas, grants);
        });
        head.append(cancel);
      }
      card.append(head);
      body.append(card);
    }

    const attached = new Set(personas.map(persona => Number(persona.id)));
    const available = (services.store.getSnapshot().library?.personas || [])
      .filter(persona => !attached.has(Number(persona.id)));
    if (available.length) {
      const row = element(documentRef, "div", "ui-tool-inline");
      const select = documentRef.createElement("select");
      select.setAttribute("aria-label", "Player persona to attach");
      for (const persona of available) {
        const option = element(documentRef, "option", "", persona.name);
        option.value = persona.id;
        markData(option);
        select.append(option);
      }
      const add = button(documentRef, COPY.add, "ui-button ui-button--primary");
      add.addEventListener("click", () => save("POST", "attach", `/api/chats/${chatId}/personas`, { persona_id: Number(select.value) }));
      row.append(select, add);
      body.append(row);
    }
    replaceLocalized(services, target, body);
  };

  void load();
  return Object.freeze({ teardown() { stopped = true; revealedInvite = null; scope.teardown(); } });
}
