/* Temporary HTML client. The service and JSON response can be reused by React. */
(() => {
  'use strict';
  const root = document.getElementById('live-editor');
  if (!root) return;
  const initial = JSON.parse(document.getElementById('live-initial').textContent);
  const status = document.getElementById('save-status');
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const inputs = new Map([...root.querySelectorAll('[data-target]')].map(el => [el.dataset.target, el]));
  const errors = new Map([...root.querySelectorAll('[data-error]')].map(el => [el.dataset.error, el]));
  const saved = new Map();
  const pending = new Map();
  const timers = new Map();
  const dirty = new Set();
  let busy = false;
  let blocked = false;

  function error(target, message) {
    errors.get(target).textContent = message;
    inputs.get(target).setAttribute('aria-invalid', message ? 'true' : 'false');
  }
  function list(container, rows) {
    if (!container) return;
    container.replaceChildren();
    for (const [name, value] of rows) {
      const line = document.createElement('p');
      line.textContent = value == null ? name : `${name}: ${value}`;
      container.append(line);
    }
    if (!rows.length) container.textContent = 'None to display.';
  }
  function render(data) {
    root.querySelectorAll('[data-output]').forEach(el => {
      el.textContent = data.outputs[el.dataset.output] ?? '—';
    });
    list(document.getElementById('effective-capabilities'), data.effective_capabilities.map(c => [c.name, c.value]));
    list(document.getElementById('trainer-capabilities'), Object.entries(data.trainer_capabilities || {}));
    const warnings = document.getElementById('live-warnings');
    warnings.hidden = !data.warnings.length;
    const ul = warnings.querySelector('ul');
    ul.replaceChildren();
    data.warnings.forEach(message => {
      const li = document.createElement('li'); li.textContent = message; ul.append(li);
    });
  }
  initial.groups.flatMap(g => g.fields).forEach(field => {
    if (!field.target) return;
    saved.set(field.target, field.value);
    const input = inputs.get(field.target);
    if (field.stage) {
      for (let stage = -6; stage <= 6; stage++) {
        input.add(new Option(stage > 0 ? `+${stage}` : String(stage), String(stage)));
      }
      // An invalid legacy stage should not silently appear to be -6.
      if (field.value < -6 || field.value > 6) input.add(new Option(`Invalid (${field.value})`, String(field.value)));
      input.value = String(field.value);
    }
  });
  render(initial);

  async function flush() {
    if (busy || blocked || !pending.size) return;
    const [target, value] = pending.entries().next().value;
    pending.delete(target);
    busy = true;
    status.textContent = 'Saving…';
    try {
      const response = await fetch(root.dataset.url, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
        body: JSON.stringify({target, value, expected: saved.get(target), active_form_id: initial.active_form_id}),
      });
      if (response.redirected) throw new Error('Your session may have expired. Log in again, then reload this sheet.');
      const data = await response.json().catch(() => { throw new Error('The server did not accept this edit. Reload to check the saved value.'); });
      if (!response.ok) {
        if (response.status === 409 || response.status === 403 || response.status === 404) blocked = true;
        throw new Error(data.error || 'Unable to save this edit.');
      }
      saved.set(target, value);
      if (Number(inputs.get(target).value) === value && inputs.get(target).value !== '') {
        dirty.delete(target); error(target, '');
      }
      render(data);
      status.textContent = dirty.size ? 'Some edits are still pending or need correction.' : 'All edits saved.';
    } catch (failure) {
      error(target, failure.message);
      status.textContent = 'An edit was not saved. Check the highlighted field. Reload if the saved value changed elsewhere.';
    } finally {
      busy = false;
      if (pending.size && !blocked) flush();
    }
  }
  function enqueue(target) {
    clearTimeout(timers.get(target)); timers.delete(target);
    const input = inputs.get(target);
    if (input.value === '' || !input.checkValidity() || !Number.isSafeInteger(Number(input.value))) {
      pending.delete(target);
      error(target, 'Enter a whole number within the displayed limits.');
      status.textContent = 'An edit needs correction and has not been saved.';
      return;
    }
    const value = Number(input.value);
    if (value === saved.get(target) && !busy) {
      pending.delete(target); dirty.delete(target); error(target, '');
      return;
    }
    error(target, '');
    pending.set(target, value);
    flush();
  }
  inputs.forEach((input, target) => {
    input.addEventListener('input', () => {
      dirty.add(target);
      pending.delete(target);
      clearTimeout(timers.get(target));
      status.textContent = 'Unsaved edit…';
      timers.set(target, setTimeout(() => enqueue(target), 650));
    });
    input.addEventListener('change', () => { dirty.add(target); enqueue(target); });
  });
  // Avoid navigating away mid-save, including switching the active form.
  document.addEventListener('submit', event => {
    if (dirty.size || busy) {
      event.preventDefault();
      status.textContent = 'Wait for edits to save, or correct the highlighted fields, before leaving or switching forms.';
    }
  });
  window.addEventListener('beforeunload', event => {
    if (dirty.size || busy) { event.preventDefault(); event.returnValue = ''; }
  });
})();
