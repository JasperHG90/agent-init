# TUI snapshot scenarios

Enumerated explicitly so coverage is visible. Each scenario gets one
`pytest-textual-snapshot` test that calls `snap_compare(...)`. To add a new
scenario: list it here AND add a test.

## Main screen
- `main_default` — landing screen, no app state required.

## Repos screen
- `repos_empty` — no repos registered.
- `repos_one` — one repo registered (fixture: local bare with one skill).

## Skills screen
- `skills_empty` — no skills indexed.
- `skills_two` — two skills indexed.
- `skills_filtered` — two skills, search bar typed "review".

## Rules screen
- `rules_empty` — no rules in library.
- `rules_with_default` — one default rule + one non-default rule.

## Conventions
- Tests use the `home` fixture so all state is sandboxed.
- Pin Textual exactly in `pyproject.toml` — renderer changes break snapshots.
- Re-record with `pytest tests/tui --snapshot-update` only after intentional
  visual changes; review the diff before committing.
