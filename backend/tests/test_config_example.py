"""`.env.example` is the only deployment documentation for configuration, so it
drifting from the Settings class is a silent operator-facing bug (a setting that
exists but nobody knows to set, or an example key the app ignores)."""
from pathlib import Path

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def _example_keys() -> set[str]:
    keys = set()
    for line in ENV_EXAMPLE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def test_every_setting_is_documented():
    missing = set(Settings.model_fields) - _example_keys()
    assert not missing, f".env.example is missing settings: {sorted(missing)}"


def test_no_stale_keys_in_example():
    stale = _example_keys() - set(Settings.model_fields)
    assert not stale, f".env.example documents keys the app ignores: {sorted(stale)}"


def test_example_parses_into_settings():
    """The documented values must actually be loadable, not just present."""
    s = Settings(_env_file=ENV_EXAMPLE)
    assert s.EMBEDDING_DIM == 384
    assert s.ALLOWED_EXTENSIONS and all(e.startswith(".") for e in s.ALLOWED_EXTENSIONS)
    assert s.CORS_ORIGINS == ["http://localhost:5173"]
    assert s.SEED_DEMO_ON_STARTUP is False
