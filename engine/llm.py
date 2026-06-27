#!/usr/bin/env python3
"""Optional Claude client for the hybrid layer — the ONE place the engine talks to an LLM.

Design rule: the engine's core (engine.py, repl.py, serve.py, build_site.py) stays pure stdlib and
deterministic. This module is imported only by the opt-in hybrid features (semantic.py, ingest.py).
If `anthropic` isn't installed or no key is configured, `available()` returns False and callers fall
back to the deterministic path — so a cold clone still runs with no key and no network.

The LLM is spent only on READING (ranking a free-text goal against cards; extracting a draft card
from a messy source). The assembled recipe, the citations, and the grounding stay deterministic in
engine.py — the LLM proposes, the grounded graph disposes. That preserves the no-counterfeit guarantee.

Key resolution mirrors Bryan's convention: ANTHROPIC_API_KEY from the environment, else from the
centralized ~/.config/llm-keys.env (which the per-project .env files symlink to).
"""
import json
import os
import re

MODEL = "claude-opus-4-8"
KEY_FILE = os.path.expanduser("~/.config/llm-keys.env")
_KEY_RE = re.compile(r"^\s*(?:export\s+)?ANTHROPIC_API_KEY\s*=\s*(.+?)\s*$")


def _load_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip().strip("\"'")
    try:
        with open(KEY_FILE) as f:
            for line in f:
                m = _KEY_RE.match(line)
                if m:
                    return m.group(1).strip().strip("\"'")
    except OSError:
        pass
    return None


def _client():
    """Return an Anthropic client, or None if the SDK or key is missing (no exception — callers
    branch on None and use the deterministic fallback)."""
    key = _load_key()
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    return anthropic.Anthropic(api_key=key)


def available():
    return _client() is not None


def json_complete(system, user, schema, max_tokens=4096):
    """One structured-output call: returns a dict validated against `schema`, or None on any failure.

    Uses output_config.format (json_schema) so the response is constrained to the schema — the LLM
    can't free-associate outside it. claude-opus-4-8 with thinking off (default) for a fast, cheap
    extraction; the schema constraint is what makes the output trustworthy, not chain-of-thought.
    """
    client = _client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if resp.stop_reason == "refusal":
            return None
        text = next((b.text for b in resp.content if b.type == "text"), None)
        return json.loads(text) if text else None
    except Exception:
        return None
