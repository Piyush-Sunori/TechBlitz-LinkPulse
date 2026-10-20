const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
const toastNode = document.getElementById('toast');
let toastTimer;

function showToast(message, error = false) {
  if (!toastNode) return;
  toastNode.textContent = message;
  toastNode.classList.toggle('error', error);
  toastNode.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastNode.classList.remove('show'), 3200);
}

async function apiRequest(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new Error(data?.detail || 'The request could not be completed.');
  return data;
}

document.querySelectorAll('[data-auth-tab]').forEach((button) => {
  button.addEventListener('click', () => {
    const registering = button.dataset.authTab === 'register';
    document.getElementById('login-form')?.classList.toggle('hidden', registering);
    document.getElementById('register-form')?.classList.toggle('hidden', !registering);
    document.querySelectorAll('[data-auth-tab]').forEach((tab) => tab.classList.toggle('active', tab === button));
  });
});

document.querySelectorAll('[data-role-choice]').forEach((button) => {
  button.addEventListener('click', () => {
    document.getElementById('login-role').value = button.dataset.roleChoice;
    document.getElementById('login-form').requestSubmit();
  });
});

document.querySelectorAll('[data-demo-role]').forEach((button) => {
  button.addEventListener('click', () => {
    const form = document.getElementById('login-form');
    form.elements.email.value = button.dataset.demoEmail;
    form.elements.password.value = button.dataset.demoPassword;
    document.getElementById('login-role').value = button.dataset.demoRole;
  });
});

document.getElementById('quick-create-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = document.getElementById('quick-value');
  const message = document.getElementById('quick-message');
  const value = input.value.trim();
  try {
    const explicitUrl = /^https?:\/\//i.test(value);
    const candidate = new URL(explicitUrl ? value : `https://${value}`);
    if (!explicitUrl && candidate.hostname === window.location.hostname && candidate.pathname !== '/') {
      window.location.assign(candidate.pathname);
      return;
    }
    if (!explicitUrl && !value.includes('/') && /^[A-Za-z0-9_-]{3,50}$/.test(value)) {
      window.location.assign(`/${value}`);
      return;
    }
    if (!explicitUrl) throw new Error('Enter a destination URL or a LinkPulse short URL.');
    const result = await apiRequest('/api/links', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ long_url: value }) });
    message.innerHTML = `Short link ready: <a class="font-semibold text-indigo-700" href="${result.short_url}">${result.short_url}</a> <button class="font-semibold text-indigo-700" data-copy="${result.short_url}">Copy</button>`;
  } catch (error) {
    if (error.message.includes('401') || error.message.toLowerCase().includes('sign in')) {
      window.location.assign('/login');
      return;
    }
    message.textContent = error.message;
    message.classList.add('text-red-600');
  }
});

document.getElementById('create-link-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  if (values.expires_at) values.expires_at = new Date(values.expires_at).toISOString();
  else delete values.expires_at;
  if (values.click_limit) values.click_limit = Number(values.click_limit);
  else delete values.click_limit;
  if (!values.password) delete values.password;
  if (!values.custom_alias) delete values.custom_alias;
  try {
    const result = await apiRequest('/api/links', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) });
    form.reset();
    showToast(`Created ${result.short_url}`);
    window.location.reload();
  } catch (error) { showToast(error.message, true); }
});

const csvFile = document.getElementById('csv-file');
csvFile?.addEventListener('change', () => {
  document.getElementById('csv-filename').textContent = csvFile.files[0]?.name || 'Drop a CSV here or browse';
});
document.getElementById('bulk-upload-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!csvFile.files.length) return;
  try {
    const result = await apiRequest('/api/links/bulk', { method: 'POST', body: new FormData(form) });
    showToast(`${result.created.length} links created; ${result.skipped.length} rows skipped.`);
    window.location.reload();
  } catch (error) { showToast(error.message, true); }
});

document.getElementById('qr-link-select')?.addEventListener('change', (event) => {
  const image = document.getElementById('qr-image');
  const placeholder = document.getElementById('qr-placeholder');
  const download = document.getElementById('qr-download');
  const id = event.target.value;
  if (!id) {
    image.classList.add('hidden'); placeholder.classList.remove('hidden'); download.classList.add('pointer-events-none', 'opacity-50'); download.href = '#';
    return;
  }
  const url = `/api/links/${encodeURIComponent(id)}/qr`;
  image.src = url;
  image.classList.remove('hidden'); placeholder.classList.add('hidden');
  download.href = url;
  download.classList.remove('pointer-events-none', 'opacity-50');
});

document.addEventListener('click', async (event) => {
  const expand = event.target.closest('[data-user-expand]');
  if (expand) {
    const row = document.getElementById(expand.dataset.userExpand);
    const open = row.classList.toggle('hidden') === false;
    expand.setAttribute('aria-expanded', String(open));
    expand.innerHTML = `<i class="fa-solid fa-chevron-${open ? 'down' : 'right'}"></i>`;
  }
  const copy = event.target.closest('[data-copy]');
  if (copy) {
    try { await navigator.clipboard.writeText(copy.dataset.copy); showToast('Short URL copied.'); }
    catch { showToast('Clipboard access was blocked.', true); }
  }
  const remove = event.target.closest('.delete-link');
  if (remove && window.confirm('Delete this link and its historical click records?')) {
    try { await apiRequest(`/api/links/${remove.dataset.id}`, { method: 'DELETE' }); window.location.reload(); }
    catch (error) { showToast(error.message, true); }
  }
  const toggle = event.target.closest('.admin-link-toggle');
  if (toggle) {
    try { await apiRequest(`/api/admin/links/${toggle.dataset.id}/toggle`, { method: 'POST' }); window.location.reload(); }
    catch (error) { showToast(error.message, true); }
  }
  const suspend = event.target.closest('.user-suspend');
  if (suspend) {
    try { await apiRequest(`/api/admin/users/${suspend.dataset.id}/suspend`, { method: 'POST' }); window.location.reload(); }
    catch (error) { showToast(error.message, true); }
  }
});

document.getElementById('blocklist-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await apiRequest('/api/admin/blocklist', { method: 'POST', body: new FormData(event.currentTarget) });
    window.location.reload();
  } catch (error) { showToast(error.message, true); }
});