# NEXTRON Security and Evidence Integrity Architecture

## Core Requirements
- Tamper-evident SHA-256 evidence sealing upon intake.
- Zero overwrite rule: all derived assets receive unique, immutable identifiers.
- Untrusted media parsing: all FFmpeg and OpenCV operations executed within isolated sandbox worker processes.
- Role-based access control (RBAC) across investigation workflows.
