import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "vercel.json").read_text())


def _csp():
    headers = CFG["headers"][0]["headers"]
    return next(h["value"] for h in headers if h["key"] == "Content-Security-Policy")


def test_platform_api_is_a_tokyo_function_reached_by_rewrite():
    assert CFG["regions"] == ["hnd1"]
    assert "api/identity.py" in CFG["functions"]
    sources = [r["source"] for r in CFG["rewrites"]]
    assert sources[0] == "/api/platform/:path*"
    assert CFG["rewrites"][0]["destination"] == "/api/identity"
    assert (ROOT / "api/identity.py").is_file()


def test_csp_allows_google_avatars_and_keeps_scripts_strict():
    csp = _csp()
    assert "img-src 'self' data: https://*.supabase.co https://*.googleusercontent.com" in csp
    assert "script-src 'self' https://cdn.jsdelivr.net;" in csp
    assert "unsafe-inline" not in csp.split("style-src")[0]


def _header(entry, key):
    return next(h["value"] for h in entry["headers"] if h["key"] == key)


def test_only_showrun_gets_the_microphone_and_direct_uploads():
    assert "microphone=()" in _header(CFG["headers"][0], "Permissions-Policy")
    assert "media-src" not in _csp()
    scoped = [e for e in CFG["headers"] if "microphone=(self)" in str(e)]
    assert [e["source"] for e in scoped] == ["/showrun(/.*)?"]
    assert "camera=()" in _header(scoped[0], "Permissions-Policy")
    csp = _header(scoped[0], "Content-Security-Policy")
    media = " media-src 'self' blob: https://*.private.blob.vercel-storage.com;"
    assert media in csp
    blob = "https://vercel.com/api/blob/"
    assert blob in csp and blob not in _csp()
    assert csp.replace(media, "").replace(f" {blob}", "") == _csp()


def test_local_only_files_are_never_deployed():
    ignored = (ROOT / ".vercelignore").read_text().split()
    for entry in (".superpowers/", ".env", ".env.*", "tests/", "db/", "scripts/", ".venv/"):
        assert entry in ignored
