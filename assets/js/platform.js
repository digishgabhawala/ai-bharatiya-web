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
  if (resp.status === 401) return null
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

export function renderAccountNav(container, me) {
  // Filled in by the account menu task.
  if (!container) return
  container.replaceChildren()
}
