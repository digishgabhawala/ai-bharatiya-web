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
