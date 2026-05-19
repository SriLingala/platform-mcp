# Contributing

Thanks for improving `platform-mcp`.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks

Run these before opening a pull request:

```bash
ruff check .
pytest
```

## Adding Knowledge

Keep the tool surface small and explicit:

- Prefer narrow, typed inputs over free-form strings.
- Keep tools read-only unless the repository documents an authorization model.
- Return structured data that an assistant can cite or summarize.
- Add tests for both valid inputs and invalid input errors.
- Avoid logging secrets, access tokens, customer data, or private incident detail.

## Pull Requests

Please include:

- A short explanation of the new tool, pattern, or runbook.
- Test coverage for changed behavior.
- Any client config or README updates needed to use the change.

