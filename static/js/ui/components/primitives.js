export function associateFieldError(control, errorElement, message) {
  if (!(control instanceof HTMLElement) || !(errorElement instanceof HTMLElement)) throw new TypeError("A control and error element are required.");
  if (!errorElement.id) errorElement.id = `${control.id || "field"}-error`;
  errorElement.textContent = message;
  errorElement.hidden = !message;
  control.setAttribute("aria-invalid", String(Boolean(message)));
  const describedBy = new Set((control.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
  if (message) describedBy.add(errorElement.id);
  else describedBy.delete(errorElement.id);
  if (describedBy.size) control.setAttribute("aria-describedby", [...describedBy].join(" "));
  else control.removeAttribute("aria-describedby");
}

export function setPressed(button, pressed) {
  button.setAttribute("aria-pressed", String(Boolean(pressed)));
}

export function setTaskState(task, state, message) {
  task.dataset.state = state;
  const stateElement = task.querySelector(".ui-task__state");
  if (stateElement) stateElement.textContent = message || state;
}
