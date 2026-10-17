"""A static server that maps clean URLs like Vercel's `cleanUrls`:
`/login` serves `login.html`, `/admin/users` serves `admin/users.html`."""
import os
from http.server import SimpleHTTPRequestHandler


class CleanUrlHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        local = super().translate_path(path)
        if not os.path.splitext(local)[1] and os.path.isfile(local + ".html"):
            return local + ".html"
        return local

    def log_message(self, format, *args):  # keep test output quiet
        pass
