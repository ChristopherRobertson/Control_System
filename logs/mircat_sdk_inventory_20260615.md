# MIRcat SDK Inventory - 2026-06-15

Day 1-4 scope only. The SDK was inventoried from `./docs`; no MIRcat service was implemented and no MIRcat device connection was opened.

## Headers

- `docs/MIRcat/SDK/include/MIRcatSDK.h`
- `docs/MIRcat/SDK/include/MIRcatGalvoSDK.h`

## Libraries and Binaries

- `docs/MIRcat/SDK/lib/MIRcatSDK.lib`
- `docs/MIRcat/SDK/bin/MIRcatSDK.dll`

## Documentation

- `docs/MIRcat/SDK/README.md`
- `docs/MIRcat/SDK/Documentation.html`
- `docs/MIRcat/SDK/MIRcatSDKGuide.pdf`
- `docs/MIRcat/SDK/docs/index.html`

## Day 5 Note

Do not copy these headers, libraries, or binaries into `control_app/` unless a later build system explicitly requires it. Day 5 MIRcat implementation should use these paths as the local SDK source of truth.

