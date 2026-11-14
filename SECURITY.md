# Security Policy

## Supported versions

This project is in early development. Security fixes are applied to the latest release on `main`.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/Sanoy24/ai-support-agent/security/advisories/new). Include:

- A description of the issue and its impact
- Steps to reproduce, or a proof of concept
- Any suggested fix

You can expect an acknowledgement within 3 business days and a status update within 10 business days.

## Scope

Issues of particular interest include:

- A customer being able to see another customer's order or personal data
- Prompt injection that makes the agent act outside its permissions
- Leaking secrets, API keys or store credentials
- Bypassing the human-handoff rules for refunds or order changes
