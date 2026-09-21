package dev.trexz.termiusbridge;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
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
    private static final String TEST_COMMAND = "printf 'TERMIUS_%s_%s\\n' 'BRIDGE' '9281'";
    private static final String MARKER = "TERMIUS_BRIDGE_9281";
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
        title.setText("Termius Bridge · R0 Pilot");
        title.setTextSize(24);
        title.setGravity(Gravity.START);
        root.addView(title);

        TextView intro = new TextView(this);
        intro.setText(
            "Objetivo: comprobar si Android puede leer el texto de una sesión de Termius mediante AccessibilityService. " +
            "Esta versión es de solo observación: no tiene permiso de Internet y no escribe comandos en Termius."
        );
        intro.setTextSize(16);
        intro.setPadding(0, dp(12), 0, dp(12));
        root.addView(intro);

        statusView = new TextView(this);
        statusView.setTextSize(16);
        statusView.setPadding(0, dp(8), 0, dp(12));
        root.addView(statusView);

        root.addView(button("1. Abrir ajustes de accesibilidad", v -> {
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
        }));

        root.addView(button("2. Abrir Termius", v -> openTermius()));

        root.addView(button("3. Copiar comando de prueba", v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("Termius Bridge test", TEST_COMMAND));
            statusView.setText("Comando copiado. Pégalo y ejecútalo dentro de Termius.");
        }));

        TextView instructions = new TextView(this);
        instructions.setText(
            "Prueba:\n" +
            "A) Activa “Termius Bridge Pilot” en Accesibilidad.\n" +
            "B) Abre tu perfil normal de Termius.\n" +
            "C) Pega el comando copiado y presiona Enter.\n" +
            "D) Regresa aquí. PASS = MARKER_FOUND: YES.\n\n" +
            "Marcador esperado: " + MARKER
        );
        instructions.setTextSize(15);
        instructions.setPadding(0, dp(14), 0, dp(14));
        root.addView(instructions);

        root.addView(button("Compartir diagnóstico", v -> shareDiagnostics()));
        root.addView(button("Borrar diagnóstico local", v -> {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().clear().apply();
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
        boolean enabled = isProbeEnabled();
        boolean connected = p.getBoolean("service_connected", false);
        boolean markerFound = p.getBoolean("marker_found", false);
        int nodeCount = p.getInt("node_count", 0);
        int inputCandidates = p.getInt("input_candidates", 0);
        long ts = p.getLong("timestamp", 0L);
        String snapshot = p.getString("snapshot", "(sin captura todavía)");

        String when = ts == 0L ? "nunca" : DateFormat.getDateTimeInstance().format(new Date(ts));
        statusView.setText(
            "ACCESSIBILITY_ENABLED: " + (enabled ? "YES" : "NO") + "\n" +
            "SERVICE_CONNECTED: " + (connected ? "YES" : "NO") + "\n" +
            "MARKER_FOUND: " + (markerFound ? "YES" : "NO") + "\n" +
            "INPUT_CANDIDATES: " + inputCandidates + "\n" +
            "NODES_VISIBLE: " + nodeCount + "\n" +
            "LAST_CAPTURE: " + when
        );

        diagnosticsView.setText(
            "=== DIAGNOSTIC SNAPSHOT ===\n" +
            "Package permitido: " + TERMIUS_PACKAGE + "\n" +
            "Marcador: " + MARKER + "\n\n" +
            snapshot
        );
    }

    private boolean isProbeEnabled() {
        AccessibilityManager manager = (AccessibilityManager) getSystemService(Context.ACCESSIBILITY_SERVICE);
        List<AccessibilityServiceInfo> services =
            manager.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK);
        for (AccessibilityServiceInfo info : services) {
            if (info.getResolveInfo() != null &&
                info.getResolveInfo().serviceInfo != null &&
                getPackageName().equals(info.getResolveInfo().serviceInfo.packageName)) {
                return true;
            }
        }
        return false;
    }

    private void openTermius() {
        PackageManager pm = getPackageManager();
        Intent launch = pm.getLaunchIntentForPackage(TERMIUS_PACKAGE);
        if (launch == null) {
            statusView.setText("No encontré Termius instalado con el paquete esperado: " + TERMIUS_PACKAGE);
            return;
        }
        startActivity(launch);
    }

    private void shareDiagnostics() {
        SharedPreferences p = getSharedPreferences(PREFS, MODE_PRIVATE);
        String text =
            "Termius Bridge Pilot R0\n" +
            "marker_found=" + p.getBoolean("marker_found", false) + "\n" +
            "input_candidates=" + p.getInt("input_candidates", 0) + "\n" +
            "node_count=" + p.getInt("node_count", 0) + "\n" +
            "timestamp=" + p.getLong("timestamp", 0L) + "\n\n" +
            p.getString("snapshot", "(sin captura)");

        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_TEXT, text);
        startActivity(Intent.createChooser(send, "Compartir diagnóstico"));
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
