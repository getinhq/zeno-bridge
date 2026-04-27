# Cross-platform QA matrix (Bridge daemon + Blender menu)

## Scope

- Web launch -> daemon launch -> DCC spawn
- Blender addon auto-bootstrap
- `Zeno` topbar menu + `Navigator`
- Login auto-start service per OS

## Matrix


| OS      | Auto-start mechanism | Daemon health       | Web launch | Blender `Zeno` menu | Navigator open |
| ------- | -------------------- | ------------------- | ---------- | ------------------- | -------------- |
| macOS   | LaunchAgent          | `GET /health` = 200 | Pass       | Pass                | Pass           |
| Linux   | systemd --user       | `GET /health` = 200 | Pass       | Pass                | Pass           |
| Windows | Task Scheduler       | `GET /health` = 200 | Pass       | Pass                | Pass           |


## Execution checklist

1. Install bridge + daemon autostart for OS.
2. Re-login machine; verify daemon starts without manual command.
3. In web app, click **Open in DCC** for a known asset.
4. Verify DCC process starts and has `ZENO_LAUNCH_CONTEXT`.
5. In Blender, confirm topbar **Zeno** menu is visible.
6. Open **Navigator**, confirm project/asset selection and load action.

