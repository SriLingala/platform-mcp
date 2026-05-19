# Security Policy

`platform-mcp` is a demo MCP server for exposing platform engineering knowledge
through read-only tools. Treat any real deployment as part of your internal
platform boundary.

## Supported Versions

Security fixes are expected to land on the `main` branch.

## Reporting a Vulnerability

Please report security issues privately before opening a public issue. If you
use this repository in an organization, route the report through your internal
security process and include:

- The affected tool or configuration.
- Whether sensitive data can be exposed.
- Reproduction steps or a minimal example.
- Suggested mitigation, if known.

## Deployment Guidance

- Run the server with the least-privileged identity needed to read its backing
  knowledge sources.
- Keep tools scoped and read-only unless you add an explicit authorization
  design.
- Do not log secrets, tokens, credentials, or private incident payloads.
- Prefer allowlists and typed inputs for tool arguments.
- Review every new data source for confidentiality before exposing it through
  MCP.

