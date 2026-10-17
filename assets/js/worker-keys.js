// Worker keys section of /account: list, create (the raw key is shown once,
// then dropped from the page) and revoke the user's Task Queue worker keys.
import { apiFetch, el, errorDetail } from '/assets/js/platform.js'

const API = '/api/queue/worker-keys'
const QUEUE_URL = 'https://ai-bharatiya-web.vercel.app/queue'

const $ = (id) => document.getElementById(id)

function formatDate(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function showError(message) {
  $('worker-keys-alert').textContent = message
  $('worker-keys-alert').hidden = !message
}

function clearNewKey() {
  $('new-key-value').textContent = ''
  $('new-key-env').textContent = ''
  $('copy-status').textContent = ''
  $('new-key').hidden = true
}

function showNewKey(rawKey) {
  $('new-key-value').textContent = rawKey
  $('new-key-env').textContent = `WORKER_API_KEY=${rawKey}\nTASK_QUEUE_URL=${QUEUE_URL}`
  $('new-key').hidden = false
  $('copy-key').focus()
}

async function copy(text, what) {
  try {
    await navigator.clipboard.writeText(text)
    $('copy-status').textContent = `${what} copied.`
  } catch {
    showError('Copying failed. Select the text and copy it by hand.')
  }
}

async function revoke(key, button) {
  button.disabled = true
  showError('')
  try {
    const resp = await apiFetch(`${API}/${encodeURIComponent(key.id)}`, { method: 'DELETE' })
    if (resp.status === 401) return
    if (!resp.ok) showError(await errorDetail(resp))
  } catch {
    showError('The key could not be revoked. Please try again.')
  }
  await loadKeys()
}

function render(keys) {
  $('worker-keys-empty').hidden = keys.length > 0
  if (keys.length === 0) {
    $('worker-keys-table').replaceChildren()
    return
  }
  const rows = keys.map((key) => {
    const status = key.revoked_at
      ? el('span', { class: 'pill pill-revoked' }, `Revoked ${formatDate(key.revoked_at)}`)
      : el('span', { class: 'pill pill-approved' }, 'Active')
    const actions = []
    if (!key.revoked_at) {
      const button = el('button', { class: 'button button-quiet button-small', type: 'button' }, 'Revoke')
      button.addEventListener('click', () => revoke(key, button))
      actions.push(button)
    }
    return el(
      'tr',
      { 'aria-label': key.name },
      el('td', {}, key.name),
      el('td', {}, el('code', {}, `${key.prefix}…`)),
      el('td', {}, formatDate(key.created_at)),
      el('td', {}, key.last_used_at ? formatDate(key.last_used_at) : 'Never'),
      el('td', {}, status),
      el('td', {}, el('div', { class: 'row-actions' }, ...actions)),
    )
  })
  const headings = ['Name', 'Key', 'Created', 'Last used', 'Status', 'Actions']
  $('worker-keys-table').replaceChildren(
    el(
      'table',
      { class: 'users-table' },
      el('thead', {}, el('tr', {}, ...headings.map((h) => el('th', { scope: 'col' }, h)))),
      el('tbody', {}, ...rows),
    ),
  )
}

async function loadKeys() {
  try {
    const resp = await apiFetch(API)
    if (resp.status === 401) return
    if (!resp.ok) {
      showError(await errorDetail(resp))
      return
    }
    render(await resp.json())
  } catch {
    showError('Your worker keys could not be loaded. Please try again shortly.')
  }
}

async function create(event) {
  event.preventDefault()
  const input = $('worker-key-name')
  const name = input.value.trim()
  if (!name) {
    input.reportValidity()
    return
  }
  const button = $('worker-key-create')
  button.disabled = true
  showError('')
  clearNewKey()
  try {
    const resp = await apiFetch(API, { method: 'POST', body: JSON.stringify({ name }) })
    if (resp.status === 401) return
    if (!resp.ok) {
      showError(await errorDetail(resp))
      return
    }
    const created = await resp.json()
    input.value = ''
    showNewKey(created.key)
    await loadKeys()
  } catch {
    showError('The key could not be created. Please try again.')
  } finally {
    button.disabled = false
  }
}

export async function startWorkerKeys() {
  $('worker-keys').hidden = false
  $('worker-key-form').addEventListener('submit', create)
  $('copy-key').addEventListener('click', () => copy($('new-key-value').textContent, 'Key'))
  $('copy-env').addEventListener('click', () => copy($('new-key-env').textContent, '.env lines'))
  $('new-key-done').addEventListener('click', clearNewKey)
  await loadKeys()
}
