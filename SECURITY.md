# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report
it privately so it can be fixed before public disclosure.

**Preferred:** use GitHub's [private vulnerability reporting](https://github.com/stultus/malayalam-factcheck-corpus/security/advisories/new).

**Alternative:** email the maintainer at hrishi.kb@gmail.com with a
description, reproduction steps, and impact assessment.

You should expect an initial response within 7 days. Please do not file
public issues for security problems.

## Scope

In scope:
- The Python pipeline (`src/`, `scripts/`)
- Project configuration (`pyproject.toml`, `configs/`)
- Workflows under `.github/workflows`

Out of scope:
- Content of the source fact-check articles (we don't author or control them)
- Vulnerabilities in upstream Python packages — please report those upstream
- Issues with the resulting Parquet artefacts that aren't security-related (open a regular issue)

## Note for data consumers

If you find that the corpus contains content that should not be redistributed
(copyright, takedown, personal data), please see [`TAKEDOWN.md`](TAKEDOWN.md)
rather than this security policy.
