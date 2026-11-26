# Security Review (Step 9, 26 November 2026)

NEXTRON runs as a single local operator without sign-in. This review covers what protects that mode and what it does not.

## Controls in place, and how each is tested

| Area | Control | Test |
|---|---|---|
| Cross-site requests | State-changing requests with a foreign `Origin` are refused (403 `ORIGIN_NOT_ALLOWED`) before any handler runs. Found in this review: CORS alone let a hostile page in the same browser submit a multipart upload. | `Integration/API/test_security.py` |
| WebSockets | Foreign `Origin` handshakes closed with 1008 (since Step 3) | `test_tmir.py` |
| Response headers | API: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-site`, `Cache-Control: no-store` on JSON. Web: the same plus `Permissions-Policy`, and a Content-Security-Policy in production builds limiting scripts, images, media and connections to the app and the API | `test_security.py`; production image checked in a browser (no console errors) |
| Abuse | 600 state-changing requests per client per minute (429 `RATE_LIMITED`, `Retry-After`) | `test_security.py` |
| Deployment | `ENVIRONMENT=production` refused unless `ALLOW_UNAUTHENTICATED_PRODUCTION=true` | `test_security.py` |
| Uploads | Signature + decode validation, size limit, safe names, read-only originals, parsers in subprocesses with timeouts | Steps 1 and 4 tests |
| SSRF | Public addresses only, numeric IP spellings parsed, pinned connections, redirect and size limits | `Unit/Backend/test_safe_fetch.py` (47 tests) |
| Model loading | Pinned SHA-256, `weights_only` loading, isolated host process | `test_detectors.py`, `test_detector_host.py` |
| Secrets | `.env` files git-ignored and kept out of Docker build contexts (`.dockerignore`); `/system/config` returns no credentials, database address or paths; the backup key is never written into a backup | `test_step8.py`, `test_backup_restore.py` |
| Backups | AES-256-GCM, authenticated chunks, restore only into new targets, verified by hashes | `test_backup_restore.py` |
| Dependencies | `pip-audit`: 88 packages, no known vulnerabilities (torch/torchvision CPU builds cannot be looked up). `npm audit`: 0 vulnerabilities (frontend and test tooling). Both run in CI | `.github/workflows/ci.yml` |
| Containers | Run as non-root users; ports bound to 127.0.0.1 | Compose smoke test |

## Not covered (open)

- **Authentication and authorisation.** Anyone who can reach the API on this machine can use it. Required before any
  network or shared deployment; the production guard exists to stop that happening by accident.
- Encryption at rest of live evidence storage and of the database (backups are encrypted).
- Malware scanning of uploads.
- Retention and deletion workflow (nothing is deletable today by design).
- TLS: everything is local HTTP.
