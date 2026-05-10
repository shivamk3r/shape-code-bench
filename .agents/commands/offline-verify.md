# Offline Verify

Run the deterministic local verification suite for this repository.

Preferred commands:

```bash
uv run pytest
uv run ruff check .
```

For scoped changes, run the narrowest relevant test first, then broaden if the
change touches shared behavior, scoring, adapters, or CLI workflows.

Do not run live API/CLI smoke tests unless explicitly requested.
