# Packaging and signing (macOS / Windows)

This document describes the **release pipeline** for Zeno Bridge binaries and installers. Exact commands depend on your certificate vendor and CI secrets.

## Goals

- **macOS:** Signed app + **notarization** so Gatekeeper accepts `zeno://` handler app.
- **Windows:** Authenticode-signed `.exe` / installer so SmartScreen trust improves.

## macOS (outline)

1. Build a minimal app bundle (PyInstaller or native wrapper) that invokes `zeno-bridge` or embeds Python.
2. **Code signing:** `codesign --deep --force --options runtime --sign "Developer ID Application: ..." ZenoBridge.app`
3. **Notarize:** `xcrun notarytool submit ZenoBridge.zip --wait` with Apple ID app-specific password.
4. **Staple:** `xcrun stapler staple ZenoBridge.app`

Store signing identity and notary credentials in CI secrets (e.g. GitHub Actions).

## Windows (outline)

1. Build `zeno-bridge.exe` (PyInstaller or equivalent).
2. Sign with **signtool** using a certificate from your CA (EV cert recommended for reputation).

```text
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a zeno-bridge.exe
```

## CI

Add a **release** workflow triggered on tags `v*` that:

1. Builds matrix: macOS (arm64 + x64), Windows x64.
2. Runs signing steps with secrets.
3. Uploads artifacts to your release storage.

This repository ships **documentation only** for signing; wire secrets in your org’s pipeline.
