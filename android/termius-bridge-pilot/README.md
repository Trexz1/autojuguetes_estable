# Termius Bridge Pilot R1

R1 tests controlled writing into a Termius Android terminal while preserving the R0 accessibility read path.

## What R1 can do
- Read the visible Termius terminal through the accessibility tree.
- Register a private Android input method named **Termius Bridge Keyboard**.
- Send one fixed, harmless marker command to Termius.
- Send Enter.
- Confirm the resulting marker from terminal output.

## What R1 cannot do
- No Internet permission.
- No arbitrary command textbox.
- No remote control.
- No SSH credentials, keys, host addresses, or Termius profiles are read.
- The IME refuses the controlled test if the current target package is not Termius.

## Pilot procedure
1. Install R1.
2. Enable **Termius Bridge Reader** under Android Accessibility.
3. Enable **Termius Bridge Keyboard** under keyboard/input-method settings.
4. Select **Termius Bridge Keyboard** as the active keyboard.
5. Open Termius and connect using an existing profile.
6. If needed, tap Termius' virtual-keyboard button.
7. On the Bridge keyboard tap **ENVIAR PRUEBA R1**.
8. Wait until the shell prompt returns.
9. Return to the R1 app.

PASS:
- `READER_ENABLED: YES`
- `IME_ENABLED: YES`
- `TERMINAL_VIEW_FOUND: YES`
- `IME_TARGET: com.server.auditor.ssh.client`
- `IME_COMMIT_OK: YES`
- `IME_ENTER_OK: YES`
- `WRITE_MARKER_FOUND: YES`

Expected output marker:
`TERMIUS_WRITE_7319`

## Privacy note
The accessibility diagnostic contains terminal text visible on screen. Review diagnostics before sharing them.
