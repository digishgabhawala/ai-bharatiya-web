"""Vercel entry point for /api/platform/* (rewritten here by vercel.json).

Not named platform.py: that would shadow the stdlib `platform` module.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # makes _platform_api importable on Vercel
from _platform_api.app import app  # noqa: F401  (Vercel serves this ASGI `app`)
