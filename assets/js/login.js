import { getClient, safeNext } from '/assets/js/platform.js'

const next = safeNext(new URLSearchParams(location.search).get('next'))
const alertBox = document.getElementById('login-alert')
const googleButton = document.getElementById('google-sign-in')
const emailToggle = document.getElementById('email-toggle')
const emailForm = document.getElementById('email-form')

function showError(message) {
  alertBox.textContent = message
  alertBox.hidden = false
}

emailToggle.addEventListener('click', () => {
  emailForm.hidden = false
  emailToggle.setAttribute('aria-expanded', 'true')
  document.getElementById('login-email').focus()
})

// Attached at once, not after the client loads: a submit before then would
// otherwise be a native GET form submit, putting the password in the URL.
emailForm.addEventListener('submit', async (event) => {
  event.preventDefault()
  alertBox.hidden = true
  const submit = emailForm.querySelector('button[type="submit"]')
  submit.disabled = true
  let client
  try {
    client = await getClient()
  } catch {
    submit.disabled = false
    showError('Sign-in is unavailable right now. Please try again shortly.')
    return
  }
  const { error } = await client.auth.signInWithPassword({
    email: emailForm.email.value.trim(),
    password: emailForm.password.value,
  })
  submit.disabled = false
  if (error) showError('Email or password is incorrect.')
})

async function start() {
  let client
  try {
    client = await getClient()
  } catch {
    showError('Sign-in is unavailable right now. Please try again shortly.')
    return
  }

  const returned = new URLSearchParams(location.search)
  const oauthError = returned.get('error_description') || returned.get('error')
  if (oauthError) showError(`Sign-in did not complete: ${oauthError}`)

  client.auth.onAuthStateChange((event, session) => {
    if (event === 'SIGNED_IN' && session) location.replace(next)
  })
  const { data } = await client.auth.getSession()
  if (data.session) {
    location.replace(next)
    return
  }

  googleButton.addEventListener('click', async () => {
    googleButton.disabled = true
    const { error } = await client.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${location.origin}/login?next=${encodeURIComponent(next)}` },
    })
    if (error) {
      googleButton.disabled = false
      showError('Google sign-in is unavailable right now.')
    }
  })

}

start()
