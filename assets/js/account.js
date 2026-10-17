import { el, getSession, goToLogin, loadMe, renderAccountNav } from '/assets/js/platform.js'

const MESSAGES = {
  pending:
    'Your account is waiting for approval. You can sign in, but the apps open once an admin approves you.',
  rejected: 'Your account was not approved.',
  suspended: "Your account is suspended. Your worker keys don't work while it is.",
  approved: 'Your account is approved.',
}
const APPS = [
  { id: 'linkedin', name: 'LinkedIn Content Agent', href: '/linkedin' },
  { id: 'queue', name: 'Task Queue', href: '/queue' },
]

async function start() {
  if (!(await getSession())) {
    goToLogin('/account')
    return
  }
  const me = await loadMe()
  if (!me) {
    goToLogin('/account')
    return
  }
  await renderAccountNav(document.getElementById('account-nav'), me)

  document.getElementById('account-title').textContent = me.display_name || me.email
  document.getElementById('account-email').textContent = me.display_name ? me.email : ''
  const status = document.getElementById('account-status')
  status.textContent = MESSAGES[me.status] || `Account status: ${me.status}`
  status.dataset.status = me.status

  const apps = document.getElementById('account-apps')
  const list = document.getElementById('account-app-list')
  const mine = me.status === 'approved' ? APPS.filter((app) => me.apps.includes(app.id)) : []
  list.replaceChildren(...mine.map((app) => el('li', {}, el('a', { href: app.href }, app.name))))
  apps.hidden = mine.length === 0
}

start().catch(() => {
  const status = document.getElementById('account-status')
  status.textContent = 'Your account could not be loaded. Please try again shortly.'
})
