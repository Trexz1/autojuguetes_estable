# Termius Bridge Pilot — frozen phases

## R0 — Accessibility Read Probe — PASS

Evidence from the pilot phone:
- Accessibility service enabled and connected.
- Termius package visible.
- `com.server.auditor.ssh.client:id/terminalView` found.
- Terminal output exposed through `contentDescription`.
- Marker `TERMIUS_BRIDGE_9281` detected from real terminal output.
- No editable accessibility input node is exposed.

Freeze:
- `R0_ACCESSIBILITY_SERVICE=PASS`
- `R0_TERMIUS_PACKAGE_VISIBILITY=PASS`
- `R0_TERMINAL_VIEW_FOUND=PASS`
- `R0_TERMINAL_OUTPUT_READ=PASS`
- `R0_MARKER_DETECTION=PASS`
- `R0_ACTION_SET_TEXT=NOT_AVAILABLE`

## R1 — Controlled Write Probe — CURRENT

Authority:
- Fixed test command only.
- No arbitrary shell textbox.
- No network permission.
- IME refuses the controlled send when the current target package is not Termius.

Write path:
- Android InputMethodService
- Termius InputConnection
- fixed command: `printf 'TERMIUS_%s_%s\n' 'WRITE' '7319'`
- Enter key event
- accessibility readback through `terminalView.contentDescription`

PASS criteria:
- `IME_TARGET=com.server.auditor.ssh.client`
- `IME_COMMIT_OK=YES`
- `IME_ENTER_OK=YES`
- `WRITE_MARKER_FOUND=YES`

Marker:
- `TERMIUS_WRITE_7319`

The literal marker is not present in the sent command, preventing the terminal's input echo from producing a false PASS.

## R2 — Local Termius Bridge
Blocked until R1 evidence is reviewed.

Potential typed operations:
- `read_terminal`
- `write_text`
- `enter`
- `interrupt`
- `wait_for`
- `send_and_wait`

R2 must add an explicit operator approval model before arbitrary text is enabled.

## R3 — Remote/MCP bridge
Blocked until a separate security freeze.

Potential scope:
- authenticated outbound-only transport
- typed tool allowlist
- human approval gates for mutations
- Hermes-specific tools preferred over unrestricted shell
- audit trail
