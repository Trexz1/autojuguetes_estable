# Termius Bridge Pilot — frozen phases

## R0 — Accessibility Probe (this APK)
Authority: observation only.

Scope:
- AccessibilityService restricted to Termius package `com.server.auditor.ssh.client`.
- Read the active accessibility node tree.
- Detect marker `TERMIUS_BRIDGE_9281`.
- Count possible text-input nodes.
- Persist only the latest diagnostic snapshot locally.
- No INTERNET permission.
- No command injection, gestures, remote API, SSH handling, credential handling, or MCP.

PASS criteria:
- `ACCESSIBILITY_ENABLED=YES`
- `SERVICE_CONNECTED=YES`
- After executing the split-marker printf command in Termius: `MARKER_FOUND=YES`

Useful partial result:
- `MARKER_FOUND=NO` + `INPUT_CANDIDATES>0`: writing may be feasible but terminal output is not exposed as accessibility text.
- `MARKER_FOUND=NO` + `INPUT_CANDIDATES=0`: Termius likely renders the terminal outside the accessible node tree.

## R1 — Controlled Input Probe
Blocked until R0 evidence is reviewed.

Potential scope:
- Set text only into an explicitly selected Termius input node.
- Separate explicit Enter action.
- Emergency stop.
- No background automation.

## R2 — Local Termius Bridge
Blocked until R1 passes.

Potential scope:
- Typed local operations: open, send, read, interrupt.
- Explicit session state and timeouts.
- Local audit log.
- No credential extraction.

## R3 — Remote/MCP bridge
Blocked until a separate security freeze.

Potential scope:
- Authenticated outbound-only transport.
- Tool allowlist.
- Human approval gates for mutations.
- Hermes-specific operations preferred over arbitrary shell.
