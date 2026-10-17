import { getSession, loadMe, renderAccountNav } from '/assets/js/platform.js'

// The home page works signed out: no redirect, just a "Sign in" link.
async function start() {
  const nav = document.getElementById('account-nav')
  let me = null
  try {
    me = (await getSession()) ? await loadMe() : null
  } catch {
    me = null
  }
  await renderAccountNav(nav, me)
}

start()
