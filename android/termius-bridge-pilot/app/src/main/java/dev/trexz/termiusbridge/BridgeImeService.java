package dev.trexz.termiusbridge;

import android.inputmethodservice.InputMethodService;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class BridgeImeService extends InputMethodService {
    private static final String TERMIUS_PACKAGE = "com.server.auditor.ssh.client";
    private static final String PREFS = "termius_probe";
    private static final String TEST_COMMAND =
        "printf 'TERMIUS_%s_%s\\n' 'WRITE' '7319'";

    private TextView statusView;

    @Override
    public View onCreateInputView() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(10), dp(12), dp(10));

        TextView title = new TextView(this);
        title.setText("Termius Bridge Keyboard · R1");
        title.setTextSize(17);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        statusView = new TextView(this);
        statusView.setText(
            "Solo prueba controlada. No registra teclas ni acepta texto arbitrario."
        );
        statusView.setTextSize(13);
        statusView.setPadding(0, dp(8), 0, dp(8));
        root.addView(statusView);

        Button test = button("ENVIAR PRUEBA R1", v -> sendControlledTest());
        root.addView(test);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);

        Button enter = button("Enter", v -> sendEnterOnly());
        LinearLayout.LayoutParams half = new LinearLayout.LayoutParams(
            0,
            LinearLayout.LayoutParams.WRAP_CONTENT,
            1f
        );
        half.setMargins(dp(3), dp(3), dp(3), dp(3));
        enter.setLayoutParams(half);
        row.addView(enter);

        Button hide = button("Ocultar", v -> requestHideSelf(0));
        LinearLayout.LayoutParams half2 = new LinearLayout.LayoutParams(
            0,
            LinearLayout.LayoutParams.WRAP_CONTENT,
            1f
        );
        half2.setMargins(dp(3), dp(3), dp(3), dp(3));
        hide.setLayoutParams(half2);
        row.addView(hide);

        root.addView(row);
        return root;
    }

    @Override
    public void onStartInput(EditorInfo attribute, boolean restarting) {
        super.onStartInput(attribute, restarting);
        if (statusView != null) {
            statusView.setText(
                "Destino: " + currentTargetPackage() +
                "\nR1 solo permite escritura cuando el destino es Termius."
            );
        }
    }

    private void sendControlledTest() {
        String target = currentTargetPackage();

        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
            .putBoolean("write_marker_found", false)
            .remove("write_marker_timestamp")
            .putLong("write_attempt_timestamp", System.currentTimeMillis())
            .putString("ime_target_package", target)
            .putBoolean("ime_commit_ok", false)
            .putBoolean("ime_enter_ok", false)
            .apply();

        if (!TERMIUS_PACKAGE.equals(target)) {
            setStatus("BLOCKED: el destino actual no es Termius.\nDestino: " + target);
            return;
        }

        InputConnection connection = getCurrentInputConnection();
        if (connection == null) {
            setStatus("BLOCKED: Termius no entregó InputConnection.");
            return;
        }

        boolean commitOk = connection.commitText(TEST_COMMAND, 1);
        boolean enterOk = false;

        if (commitOk) {
            enterOk = sendEnter(connection);
        }

        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
            .putBoolean("ime_commit_ok", commitOk)
            .putBoolean("ime_enter_ok", enterOk)
            .apply();

        setStatus(
            "TEST_SENT\ncommitText=" + commitOk +
            "\nenter=" + enterOk +
            "\nEspera el prompt y vuelve a Termius Bridge R1."
        );
    }

    private void sendEnterOnly() {
        String target = currentTargetPackage();
        if (!TERMIUS_PACKAGE.equals(target)) {
            setStatus("BLOCKED: Enter solo se envía a Termius.");
            return;
        }

        InputConnection connection = getCurrentInputConnection();
        if (connection == null) {
            setStatus("BLOCKED: sin InputConnection.");
            return;
        }

        boolean ok = sendEnter(connection);
        setStatus("ENTER_SENT=" + ok);
    }

    private boolean sendEnter(InputConnection connection) {
        long now = SystemClock.uptimeMillis();

        KeyEvent down = new KeyEvent(
            now,
            now,
            KeyEvent.ACTION_DOWN,
            KeyEvent.KEYCODE_ENTER,
            0
        );
        KeyEvent up = new KeyEvent(
            now,
            SystemClock.uptimeMillis(),
            KeyEvent.ACTION_UP,
            KeyEvent.KEYCODE_ENTER,
            0
        );

        boolean downOk = connection.sendKeyEvent(down);
        boolean upOk = connection.sendKeyEvent(up);
        return downOk && upOk;
    }

    private String currentTargetPackage() {
        EditorInfo info = getCurrentInputEditorInfo();
        if (info == null || info.packageName == null) {
            return "(sin destino)";
        }
        return info.packageName;
    }

    private void setStatus(String value) {
        if (statusView != null) {
            statusView.setText(value);
        }
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
        lp.setMargins(dp(3), dp(3), dp(3), dp(3));
        b.setLayoutParams(lp);
        return b;
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}
