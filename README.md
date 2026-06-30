mega.io.py
==========

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Unofficial, community-maintained fork of [mega.py](https://github.com/odwyersoftware/mega.py).**
Not affiliated with, nor endorsed by, MEGA. For the official command-line client see
[MEGAcmd](https://mega.io/cmd).

A lightweight, pure-Python library for the [MEGA](https://mega.nz) cloud storage API.

Features
--------

These are implemented today:

-   **Modern login** — v2 accounts (PBKDF2-HMAC-SHA512 with a per-user salt),
    legacy v1 accounts, two-factor (TOTP) accounts, and anonymous temporary
    sessions.
-   **End-to-end encryption** — per-node keys, RSA session unwrapping, AES-CBC
    attribute decryption, and AES-CTR file content with chunked MAC integrity
    checks.
-   **Streaming transfers** — chunked upload and download with near-constant
    memory use, independent of file size, to and from either a filesystem path
    or a binary file-like object (e.g. `io.BytesIO`). Interrupted downloads can
    be resumed with `download(..., resume=True)` (re-fetches only the missing
    bytes via HTTP Range).
-   **File operations** — fetch the node tree, resolve nodes by path, create
    folders, upload, download, move, rename, delete (to the Rubbish Bin) and
    permanently destroy.
-   **Public links** — export a *file* to a public link, and import from a
    public URL. (Folder links are not supported — see Roadmap.)
-   **Resilient** — automatic retry with exponential backoff on MEGA's
    rate-limit / "try again" (`EAGAIN`) responses.
-   **Lightweight** — pure Python; AES and RSA come from a standalone crypto
    library (pycryptodome). It does not bundle or compile MEGA's C++ SDK.

Roadmap
-------

The following are **planned but not yet implemented** — do not rely on them yet:

-   Resumable uploads (downloads can already be resumed).
-   Folder public links / shared folders — creating a folder share requires
    MEGA's Key Manager (the encrypted `^!keys` keyring), which this library does
    not implement, so the API rejects it. Only individual *file* links work
    today.

Non-goals
---------

-   **Solving MEGA's proof-of-work (HTTP 402) challenges.** They are detected
    and surfaced as a clear `HashcashError`, but solving them is intentionally
    out of scope: a normal user never needs it, and the abusive/bot traffic it
    throttles is not a use case this library aims to serve.

Usage
-----

See the usage guide: [doc/USAGE.md](doc/USAGE.md).

For API and protocol details see [doc/API_INFO.md](doc/API_INFO.md).

Support
-------

Please report bugs and ask questions via GitHub Issues:
<https://github.com/atallo/mega.io.py/issues>

License
-------

Licensed under the Apache License 2.0 — see [LICENSE](LICENSE).

This project is an unofficial fork of `mega.py` by O'Dwyer Software, used under
the Apache 2.0 license; original attribution is retained.
