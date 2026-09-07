# Contributing

Contributions are welcome, especially focused fixes that preserve BlendSmith's authority boundaries and model-neutral contracts.

## Development setup

```bash
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m pytest -q
```

Before opening a pull request:

- keep lifecycle and integrity checks fail-closed;
- do not move human approval into an agent/model decision;
- add or update tests for state, path, SHA, checkpoint, or contract changes;
- update public schemas/docs when a contract changes;
- avoid model-specific reasoning formats in Core contracts.

For security-sensitive findings, follow [SECURITY.md](SECURITY.md) rather than publishing exploit details in an issue.
