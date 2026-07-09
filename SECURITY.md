# Security Policy

## Supported Versions

The `main` branch is supported while the project is in alpha.

## Reporting a Vulnerability

Please do not open public issues for vulnerabilities involving secret leakage, credential handling, or unsafe file writes.

Report privately to the maintainer listed in the repository profile. If no private channel is configured yet, open a minimal public issue that says a private security report is needed, without technical details.

## Secrets

ClipScript reads provider secrets from environment variables. Never commit:

- `.env`;
- API keys;
- generated logs containing secrets;
- cached provider responses that may include sensitive metadata.
