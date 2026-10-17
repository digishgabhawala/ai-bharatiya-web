// Shared sign-in plumbing for the suite's own pages (/login, /account, /admin/users, /).
// Uses the supabase-js UMD build (window.supabase), loaded by each page before this module.
// Default session storage is shared by every app on this origin, so one sign-in covers all.

let configPromise = null
let clientPromise = null

export function loadConfig() {
  configPromise ??= fetch('/api/platform/config').then((resp) => {
    if (!resp.ok) throw new Error(`config ${resp.status}`)
    return resp.json()
  })
  return configPromise
}

export function getClient() {
  clientPromise ??= loadConfig().then((cfg) =>
    window.supabase.createClient(cfg.supabase_url, cfg.supabase_publishable_key, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        flowType: 'pkce',
      },
    }),
  )
  return clientPromise
}

export async function getSession() {
  const client = await getClient()
  const { data } = await client.auth.getSession()
  return data.session
}

// Only a same-origin path survives; anything else (other origins, `//host`,
// backslash tricks, `javascript:`) goes home.
export function safeNext(raw, origin = location.origin) {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) return '/'
  try {
    const url = new URL(raw, origin)
    return url.origin === origin ? url.pathname + url.search + url.hash : '/'
  } catch {
    return '/'
  }
}

export function goToLogin(next = location.pathname + location.search) {
  location.assign(`/login?next=${encodeURIComponent(safeNext(next))}`)
}

// The server rejected our session (401): forget it locally first, otherwise
// /login would see the stored session and bounce straight back here.
async function dropRejectedSession() {
  try {
    const client = await getClient()
    await client.auth.signOut({ scope: 'local' })
  } catch {
    // nothing stored, or storage unavailable: nothing to forget
  }
}

export async function apiFetch(path, init = {}, { redirectOn401 = true } = {}) {
  const session = await getSession()
  const headers = new Headers(init.headers || {})
  if (session) headers.set('Authorization', `Bearer ${session.access_token}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const resp = await fetch(path, { ...init, headers })
  if (resp.status === 401 && redirectOn401) {
    await dropRejectedSession()
    goToLogin()
  }
  return resp
}

export async function signOut() {
  try {
    const client = await getClient()
    await client.auth.signOut()
  } catch {
    // signing out must always reach /login
  }
  location.assign('/login')
}

// The signed-in user's profile, or null when there is no (valid) session.
export async function loadMe() {
  const resp = await apiFetch('/api/platform/me', {}, { redirectOn401: false })
  if (resp.status === 401) {
    await dropRejectedSession()
    return null
  }
  if (!resp.ok) throw new Error(`me ${resp.status}`)
  return resp.json()
}

export async function errorDetail(resp) {
  try {
    const body = await resp.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // not JSON
  }
  return `Request failed (${resp.status})`
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag)
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue
    if (key === 'class') node.className = value
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value)
    else node.setAttribute(key, value === true ? '' : value)
  }
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false))
  return node
}

export function isAdmin(me) {
  return Boolean(me && me.is_admin && me.status === 'approved')
}

// Admins see how many sign-ups are waiting. Failures just leave the badge off.
export async function refreshPendingBadge(container) {
  const link = container && container.querySelector('[data-admin-link]')
  if (!link) return
  let count = 0
  try {
    const resp = await apiFetch('/api/platform/users?status=pending', {}, { redirectOn401: false })
    if (resp.ok) count = (await resp.json()).length
  } catch {
    count = 0
  }
  link.querySelector('.badge')?.remove()
  if (count > 0) {
    link.setAttribute('aria-label', `Admin ${count} pending`)
    link.append(el('span', { class: 'badge', 'aria-hidden': 'true' }, String(count)))
  } else {
    link.removeAttribute('aria-label')
  }
}

// The suite header's account menu. `me` null means signed out.
export async function renderAccountNav(container, me) {
  if (!container) return
  if (!me) {
    const next = encodeURIComponent(location.pathname + location.search)
    container.replaceChildren(el('a', { class: 'nav-cta', href: `/login?next=${next}` }, 'Sign in'))
    return
  }
  const label = me.display_name || me.email || 'Account'
  const avatar = me.avatar_url
    ? el('img', { class: 'avatar', src: me.avatar_url, alt: '', referrerpolicy: 'no-referrer' })
    : el('span', { class: 'avatar', 'aria-hidden': 'true' }, label.charAt(0).toUpperCase())
  const items = [
    el('span', { class: 'account-who' }, avatar, el('span', { class: 'account-name' }, label)),
    el('a', { href: '/account' }, 'Account'),
  ]
  if (isAdmin(me)) items.push(el('a', { href: '/admin/users', 'data-admin-link': true }, 'Admin'))
  items.push(el('button', { class: 'link-button', type: 'button', onclick: () => signOut() }, 'Sign out'))
  container.replaceChildren(...items)
  if (isAdmin(me)) await refreshPendingBadge(container)
}
