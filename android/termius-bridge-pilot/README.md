# Termius Bridge Pilot R0

Private pilot APK to verify whether Termius Android exposes terminal text and an input node through Android Accessibility APIs.

## Install
1. Install the APK.
2. Open **Termius Bridge Pilot**.
3. Tap **Abrir ajustes de accesibilidad**.
4. Enable **Termius Bridge Pilot**.
5. Return to the app and confirm `ACCESSIBILITY_ENABLED: YES`.
6. Tap **Copiar comando de prueba**.
7. Open Termius, connect with an existing profile, paste the command and press Enter.
8. Return to the pilot.

Expected PASS:
- `SERVICE_CONNECTED: YES`
- `MARKER_FOUND: YES`

The test command is intentionally split so the literal expected marker is not present in the command text itself.

## Security properties
- No `INTERNET` permission.
- Accessibility events are scoped to the Termius Android package.
- R0 never performs `ACTION_SET_TEXT`, clicks, gestures, shell execution, SSH configuration, or credential access.
- The latest accessibility snapshot is stored only in the app's private SharedPreferences.
- The diagnostic can be cleared from the app at any time.

## Important
Accessibility snapshots can contain text visible inside the Termius UI. Treat shared diagnostics as potentially sensitive and review them before sending them anywhere.
