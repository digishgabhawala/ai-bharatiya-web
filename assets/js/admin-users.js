import {
  apiFetch,
  el,
  errorDetail,
  getSession,
  goToLogin,
  isAdmin,
  loadMe,
  refreshPendingBadge,
  renderAccountNav,
} from '/assets/js/platform.js'

const statusLine = document.getElementById('users-status')
const alertBox = document.getElementById('users-alert')
const tableWrap = document.getElementById('users-table')
const nav = document.getElementById('account-nav')
const STATUS_LABELS = { pending: 'Pending', approved: 'Approved', rejected: 'Rejected', suspended: 'Suspended' }

let me = null

// Only actions that are legal for the row's current state (see transitions.py).
// Own row: none (admins can't change their own status or admin flag).
function actionsFor(user) {
  if (user.user_id === me.user_id) return []
  switch (user.status) {
    case 'pending':
      return [{ label: 'Approve', action: 'approve' }, { label: 'Reject', action: 'reject' }]
    case 'approved':
      return [
        { label: 'Suspend', action: 'suspend' },
        user.is_admin
          ? { label: 'Remove admin', admin: false }
          : { label: 'Make admin', admin: true },
      ]
    case 'rejected':
      return [{ label: 'Approve', action: 'approve' }]
    case 'suspended':
      return [{ label: 'Reinstate', action: 'reinstate' }]
    default:
      return []
  }
}

function showError(message) {
  alertBox.textContent = message
  alertBox.hidden = false
}

function formatDate(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

async function run(user, item, button) {
  button.disabled = true
  alertBox.hidden = true
  try {
    const resp =
      'admin' in item
        ? await apiFetch(`/api/platform/users/${encodeURIComponent(user.user_id)}/admin`, {
            method: 'POST',
            body: JSON.stringify({ is_admin: item.admin }),
          })
        : await apiFetch(`/api/platform/users/${encodeURIComponent(user.user_id)}/${item.action}`, {
            method: 'POST',
          })
    if (!resp.ok) showError(await errorDetail(resp))
  } catch {
    showError('The change could not be sent. Please try again.')
  }
  await loadUsers()
  await refreshPendingBadge(nav)
}

function render(users) {
  const pending = users.filter((u) => u.status === 'pending').length
  statusLine.textContent = `${users.length} ${users.length === 1 ? 'user' : 'users'}, ${pending} pending`
  const rows = users.map((user) => {
    const name = user.display_name || user.email || user.user_id
    const label = user.display_name && user.email ? `${user.display_name} (${user.email})` : name
    const buttons = actionsFor(user).map((item) => {
      const button = el('button', { class: 'button button-quiet button-small', type: 'button' }, item.label)
      button.addEventListener('click', () => run(user, item, button))
      return button
    })
    const badges = [el('span', { class: `pill pill-${user.status}` }, STATUS_LABELS[user.status] || user.status)]
    if (user.is_admin) badges.push(el('span', { class: 'pill' }, 'Admin'))
    return el(
      'tr',
      { 'aria-label': label },
      el('td', {}, name),
      el('td', {}, user.email || ''),
      el('td', {}, ...badges),
      el('td', {}, formatDate(user.created_at)),
      el('td', {}, el('div', { class: 'row-actions' }, ...buttons)),
    )
  })
  const table = el(
    'table',
    { class: 'users-table' },
    el(
      'thead',
      {},
      el('tr', {}, ...['Name', 'Email', 'Status', 'Created', 'Actions'].map((h) => el('th', { scope: 'col' }, h))),
    ),
    el('tbody', {}, ...rows),
  )
  tableWrap.replaceChildren(table)
}

async function loadUsers() {
  const resp = await apiFetch('/api/platform/users')
  if (resp.status === 401) return
  if (!resp.ok) {
    showError(await errorDetail(resp))
    return
  }
  render(await resp.json())
}

async function start() {
  if (!(await getSession())) {
    goToLogin('/admin/users')
    return
  }
  me = await loadMe()
  if (!me) {
    goToLogin('/admin/users')
    return
  }
  await renderAccountNav(nav, me)
  if (!isAdmin(me)) {
    statusLine.textContent = 'Admins only. Your account can’t manage users.'
    return
  }
  await loadUsers()
}

start().catch(() => {
  statusLine.textContent = 'Users could not be loaded. Please try again shortly.'
})
