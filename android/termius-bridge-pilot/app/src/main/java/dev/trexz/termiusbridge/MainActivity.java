package dev.trexz.termiusbridge;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.view.accessibility.AccessibilityManager;

import java.text.DateFormat;
import java.util.Date;
import java.util.List;

public class MainActivity extends Activity {
    private static final String TERMIUS_PACKAGE = "com.server.auditor.ssh.client";
    private static final String WRITE_MARKER = "TERMIUS_WRITE_7319";
    private static final String PREFS = "termius_probe";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView statusView;
    private TextView diagnosticsView;

    private final Runnable refresher = new Runnable() {
        @Override
        public void run() {
            refresh();
            handler.postDelayed(this, 1000);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(20), dp(20), dp(20));
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("Termius Bridge · R1 Controlled Write");
        title.setTextSize(24);
        title.setGravity(Gravity.START);
        root.addView(title);

        TextView intro = new TextView(this);
        intro.setText(
            "R0 confirmó lectura real del terminal mediante terminalView.contentDescription. " +
            "R1 añade un teclado privado del bridge para probar escritura + Enter. " +
            "No tiene permiso de Internet y el teclado se niega a enviar la prueba si la app destino no es Termius."
        );
        intro.setTextSize(16);
        intro.setPadding(0, dp(12), 0, dp(12));
        root.addView(intro);

        statusView = new TextView(this);
        statusView.setTextSize(16);
        statusView.setPadding(0, dp(8), 0, dp(12));
        root.addView(statusView);

        root.addView(button("1. Activar lector de Termius", v -> {
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
        }));

        root.addView(button("2. Habilitar teclado Bridge", v -> {
            startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS));
        }));

        root.addView(button("3. Elegir teclado Bridge", v -> {
            InputMethodManager imm =
                (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            imm.showInputMethodPicker();
        }));

        root.addView(button("4. Abrir Termius", v -> openTermius()));

        TextView instructions = new TextView(this);
        instructions.setText(
            "Prueba R1:\n" +
            "A) Confirma READER=YES e IME_ENABLED=YES.\n" +
            "B) Elige “Termius Bridge Keyboard”.\n" +
            "C) Abre una sesión normal de Termius.\n" +
            "D) Toca el botón de teclado virtual de Termius si el teclado no aparece.\n" +
            "E) En nuestro teclado toca “ENVIAR PRUEBA R1”.\n" +
            "F) Espera a que reaparezca el prompt y regresa aquí.\n\n" +
            "PASS = WRITE_MARKER_FOUND: YES\n" +
            "Marcador esperado: " + WRITE_MARKER + "\n\n" +
            "El comando que envía el teclado está fragmentado para que el eco del comando no pueda producir un falso PASS."
        );
        instructions.setTextSize(15);
        instructions.setPadding(0, dp(14), 0, dp(14));
        root.addView(instructions);

        root.addView(button("Compartir diagnóstico R1", v -> shareDiagnostics()));

        root.addView(button("Reiniciar resultado R1", v -> {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .remove("write_marker_found")
                .remove("write_marker_timestamp")
                .remove("write_attempt_timestamp")
                .remove("ime_target_package")
                .remove("ime_commit_ok")
                .remove("ime_enter_ok")
                .apply();
            refresh();
        }));

        diagnosticsView = new TextView(this);
        diagnosticsView.setTextSize(13);
        diagnosticsView.setTextIsSelectable(true);
        diagnosticsView.setPadding(0, dp(16), 0, dp(24));
        root.addView(diagnosticsView);

        setContentView(scroll);
    }

    @Override
    protected void onResume() {
        super.onResume();
        handler.removeCallbacks(refresher);
        handler.post(refresher);
    }

    @Override
    protected void onPause() {
        handler.removeCallbacks(refresher);
        super.onPause();
    }

    private void refresh() {
        SharedPreferences p = getSharedPreferences(PREFS, MODE_PRIVATE);
        boolean readerEnabled = isProbeEnabled();
        boolean imeEnabled = isBridgeImeEnabled();
        boolean connected = p.getBoolean("service_connected", false);
        boolean terminalViewFound = p.getBoolean("terminal_view_found", false);
        boolean r0MarkerFound = p.getBoolean("r0_marker_found", false);
        boolean writeMarkerFound = p.getBoolean("write_marker_found", false);
        boolean imeCommitOk = p.getBoolean("ime_commit_ok", false);
        boolean imeEnterOk = p.getBoolean("ime_enter_ok", false);
        String imeTarget = p.getString("ime_target_package", "(sin intento)");
        int nodeCount = p.getInt("node_count", 0);
        int inputCandidates = p.getInt("input_candidates", 0);
        long ts = p.getLong("timestamp", 0L);
        long writeTs = p.getLong("write_marker_timestamp", 0L);
        long attemptTs = p.getLong("write_attempt_timestamp", 0L);
        String snapshot = p.getString("snapshot", "(sin captura todavía)");

        String when = ts == 0L ? "nunca" : DateFormat.getDateTimeInstance().format(new Date(ts));
        String writeWhen =
            writeTs == 0L ? "nunca" : DateFormat.getDateTimeInstance().format(new Date(writeTs));
        String attemptWhen =
            attemptTs == 0L ? "nunca" : DateFormat.getDateTimeInstance().format(new Date(attemptTs));

        statusView.setText(
            "READER_ENABLED: " + (readerEnabled ? "YES" : "NO") + "\n" +
            "IME_ENABLED: " + (imeEnabled ? "YES" : "NO") + "\n" +
            "SERVICE_CONNECTED: " + (connected ? "YES" : "NO") + "\n" +
            "TERMINAL_VIEW_FOUND: " + (terminalViewFound ? "YES" : "NO") + "\n" +
            "R0_READ_MARKER_FOUND: " + (r0MarkerFound ? "YES" : "NO") + "\n" +
            "WRITE_MARKER_FOUND: " + (writeMarkerFound ? "YES" : "NO") + "\n" +
            "IME_TARGET: " + imeTarget + "\n" +
            "IME_COMMIT_OK: " + (imeCommitOk ? "YES" : "NO") + "\n" +
            "IME_ENTER_OK: " + (imeEnterOk ? "YES" : "NO") + "\n" +
            "WRITE_ATTEMPT_AT: " + attemptWhen + "\n" +
            "INPUT_CANDIDATES: " + inputCandidates + "\n" +
            "NODES_VISIBLE: " + nodeCount + "\n" +
            "LAST_CAPTURE: " + when + "\n" +
            "WRITE_PASS_AT: " + writeWhen
        );

        diagnosticsView.setText(
            "=== R1 DIAGNOSTIC SNAPSHOT ===\n" +
            "Package permitido: " + TERMIUS_PACKAGE + "\n" +
            "Write marker: " + WRITE_MARKER + "\n\n" +
            snapshot
        );
    }

    private boolean isProbeEnabled() {
        AccessibilityManager manager =
            (AccessibilityManager) getSystemService(Context.ACCESSIBILITY_SERVICE);
        List<AccessibilityServiceInfo> services =
            manager.getEnabledAccessibilityServiceList(
                AccessibilityServiceInfo.FEEDBACK_ALL_MASK
            );
        for (AccessibilityServiceInfo info : services) {
            if (info.getResolveInfo() != null &&
                info.getResolveInfo().serviceInfo != null &&
                getPackageName().equals(
                    info.getResolveInfo().serviceInfo.packageName
                )) {
                return true;
            }
        }
        return false;
    }

    private boolean isBridgeImeEnabled() {
        InputMethodManager imm =
            (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        List<InputMethodInfo> methods = imm.getEnabledInputMethodList();
        for (InputMethodInfo info : methods) {
            if (info.getServiceInfo() != null &&
                getPackageName().equals(info.getServiceInfo().packageName) &&
                BridgeImeService.class.getName().equals(
                    info.getServiceInfo().name
                )) {
                return true;
            }
        }
        return false;
    }

    private void openTermius() {
        PackageManager pm = getPackageManager();
        Intent launch = pm.getLaunchIntentForPackage(TERMIUS_PACKAGE);
        if (launch == null) {
            statusView.setText(
                "No encontré Termius instalado con el paquete esperado: " +
                TERMIUS_PACKAGE
            );
            return;
        }
        startActivity(launch);
    }

    private void shareDiagnostics() {
        SharedPreferences p = getSharedPreferences(PREFS, MODE_PRIVATE);
        String text =
            "Termius Bridge Pilot R1\n" +
            "reader_enabled=" + isProbeEnabled() + "\n" +
            "ime_enabled=" + isBridgeImeEnabled() + "\n" +
            "service_connected=" + p.getBoolean("service_connected", false) + "\n" +
            "terminal_view_found=" + p.getBoolean("terminal_view_found", false) + "\n" +
            "r0_marker_found=" + p.getBoolean("r0_marker_found", false) + "\n" +
            "write_marker_found=" + p.getBoolean("write_marker_found", false) + "\n" +
            "ime_target_package=" + p.getString("ime_target_package", "(sin intento)") + "\n" +
            "ime_commit_ok=" + p.getBoolean("ime_commit_ok", false) + "\n" +
            "ime_enter_ok=" + p.getBoolean("ime_enter_ok", false) + "\n" +
            "write_attempt_timestamp=" + p.getLong("write_attempt_timestamp", 0L) + "\n" +
            "input_candidates=" + p.getInt("input_candidates", 0) + "\n" +
            "node_count=" + p.getInt("node_count", 0) + "\n" +
            "timestamp=" + p.getLong("timestamp", 0L) + "\n" +
            "write_marker_timestamp=" + p.getLong("write_marker_timestamp", 0L) +
            "\n\n" +
            p.getString("snapshot", "(sin captura)");

        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_TEXT, text);
        startActivity(Intent.createChooser(send, "Compartir diagnóstico R1"));
    }

    private Button button(String text, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setOnClickListener(listener);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        lp.setMargins(0, dp(5), 0, dp(5));
        b.setLayoutParams(lp);
        return b;
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}
