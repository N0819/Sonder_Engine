let fieldSequence = 0;

export function decorateFieldControl(control) {
  if (!(control instanceof HTMLElement)) {
    throw new TypeError("A field control element is required.");
  }
  control.classList.add("ui-field__control");
  control.classList.remove("ui-input");
  return control;
}

export function createField(documentRef, options = {}) {
  if (!documentRef?.createElement) throw new TypeError("A document is required.");
  const wrapper = documentRef.createElement("label");
  wrapper.className = ["ui-field", options.className].filter(Boolean).join(" ");

  const label = documentRef.createElement("span");
  label.className = "ui-field__label";
  label.textContent = String(options.label || "");

  const tagName = options.tagName === "textarea" || options.tagName === "select"
    ? options.tagName : "input";
  const control = decorateFieldControl(documentRef.createElement(tagName));
  control.id = options.id || `ui-field-${++fieldSequence}`;
  if (tagName === "input") control.type = options.type || "text";
  if (options.name) control.name = options.name;
  if (options.placeholder) control.placeholder = options.placeholder;
  if (options.value !== undefined && tagName !== "select") control.value = options.value;
  if (options.controlClassName) control.classList.add(...options.controlClassName.split(/\s+/));
  if (options.label) control.setAttribute("aria-label", options.label);
  wrapper.append(label, control);

  let help = null;
  if (options.help) {
    help = documentRef.createElement("span");
    help.className = "ui-field__help";
    help.id = `${control.id}-help`;
    help.textContent = options.help;
    control.setAttribute("aria-describedby", help.id);
    wrapper.append(help);
  }
  return Object.freeze({ element: wrapper, label, control, help });
}
