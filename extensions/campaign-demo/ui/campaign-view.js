// The campaign panel: mission state, and only what this player has.

const STATUS_LABEL = {
  locked: "Locked",
  available: "Available",
  done: "Complete"
};

export function createCampaignView(sonder) {
  return {
    id: "campaign-demo",
    label: "Campaign",
    render: (container) => draw(sonder, container)
  };
}

async function draw(sonder, container) {
  container.innerHTML = "";
  const root = el("div", "campaign-demo");
  container.appendChild(root);

  let data;
  try {
    const { chatId } = sonder.state();
    data = await sonder.call("GET", "/x/campaign"
      + "?chat_id=" + encodeURIComponent(chatId || ""));
  } catch (err) {
    root.appendChild(el("p", "campaign-demo__note", "Could not read the campaign."));
    return;
  }

  if (!data || !data.campaign) {
    root.appendChild(el("p", "campaign-demo__note",
      "This story is not a campaign of ours."));
    const start = el("button", "campaign-demo__start", "Start “The Sealed Wing”");
    start.addEventListener("click", async () => {
      start.disabled = true;
      const made = await sonder.call("POST", "/x/start", {});
      // The host owns which story is open; a campaign that navigated on its own
      // would be deciding that for a player who might be mid-beat elsewhere.
      root.appendChild(el("p", "campaign-demo__note",
        "Created “" + (made.name || "the campaign") + "”. Open it from Stories."));
    });
    root.appendChild(start);
    return;
  }

  root.appendChild(el("h2", "campaign-demo__title", "The Sealed Wing"));
  root.appendChild(el("p", "campaign-demo__meta",
    "Player authority: " + data.authority
    + (data.turn === undefined || data.turn === null ? "" : " · turn " + data.turn)));

  const list = el("ul", "campaign-demo__objectives");
  for (const objective of data.objectives || []) {
    const item = el("li", "campaign-demo__objective campaign-demo__objective--"
      + (objective.status || "locked"));
    item.appendChild(el("span", "campaign-demo__status",
      STATUS_LABEL[objective.status] || objective.status));
    item.appendChild(el("span", "campaign-demo__objective-title", objective.title));
    list.appendChild(item);
  }
  root.appendChild(list);

  // Absent keys stay absent. The projection omits what this player does not
  // have, and a panel that filled the gap with "Unknown" would be making a
  // claim the engine declined to make.
  if (data.where) {
    root.appendChild(el("p", "campaign-demo__where", "You are in " + data.where + "."));
  }
  if ((data.knows || []).length) {
    root.appendChild(el("p", "campaign-demo__knows",
      "You can name: " + data.knows.join(", ")));
  }
  if (data.view) {
    root.appendChild(el("pre", "campaign-demo__view", data.view));
  }
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
