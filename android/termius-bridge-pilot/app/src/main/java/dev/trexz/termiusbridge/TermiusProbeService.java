package dev.trexz.termiusbridge;

import android.accessibilityservice.AccessibilityService;
import android.content.SharedPreferences;
import android.os.Build;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.List;

public class TermiusProbeService extends AccessibilityService {
    private static final String TERMIUS_PACKAGE = "com.server.auditor.ssh.client";
    private static final String MARKER = "TERMIUS_BRIDGE_9281";
    private static final String PREFS = "termius_probe";
    private static final int MAX_NODES = 600;
    private static final int MAX_CHARS = 48000;

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        prefs().edit().putBoolean("service_connected", true).apply();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null || event.getPackageName() == null) {
            return;
        }
        if (!TERMIUS_PACKAGE.contentEquals(event.getPackageName())) {
            return;
        }

        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) {
            root = event.getSource();
        }
        if (root == null) {
            saveEmpty("Termius event received, but root node is null.");
            return;
        }

        capture(root, event);
    }

    @Override
    public void onInterrupt() {
        prefs().edit().putBoolean("service_connected", false).apply();
    }

    @Override
    public void onDestroy() {
        prefs().edit().putBoolean("service_connected", false).apply();
        super.onDestroy();
    }

    private void capture(AccessibilityNodeInfo root, AccessibilityEvent event) {
        Deque<NodeDepth> queue = new ArrayDeque<>();
        queue.add(new NodeDepth(root, 0));

        StringBuilder out = new StringBuilder();
        int nodes = 0;
        int inputCandidates = 0;
        boolean markerFound = false;

        while (!queue.isEmpty() && nodes < MAX_NODES && out.length() < MAX_CHARS) {
            NodeDepth current = queue.removeFirst();
            AccessibilityNodeInfo node = current.node;
            if (node == null) {
                continue;
            }

            nodes++;
            CharSequence text = node.getText();
            CharSequence desc = node.getContentDescription();
            CharSequence cls = node.getClassName();
            String viewId = node.getViewIdResourceName();

            boolean setTextCapable = supportsAction(node, AccessibilityNodeInfo.ACTION_SET_TEXT);
            boolean candidate = node.isEditable() || setTextCapable;
            if (candidate) {
                inputCandidates++;
            }

            String textValue = safe(text);
            String descValue = safe(desc);
            if (textValue.contains(MARKER) || descValue.contains(MARKER)) {
                markerFound = true;
            }

            indent(out, current.depth);
            out.append("#").append(nodes)
                .append(" class=").append(safe(cls))
                .append(" text=").append(quote(textValue))
                .append(" desc=").append(quote(descValue))
                .append(" id=").append(viewId == null ? "" : viewId)
                .append(" editable=").append(node.isEditable())
                .append(" focusable=").append(node.isFocusable())
                .append(" clickable=").append(node.isClickable())
                .append(" setText=").append(setTextCapable)
                .append("\n");

            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) {
                    queue.addLast(new NodeDepth(child, current.depth + 1));
                }
            }
        }

        String header =
            "eventType=" + AccessibilityEvent.eventTypeToString(event.getEventType()) + "\n" +
            "package=" + safe(event.getPackageName()) + "\n" +
            "marker=" + MARKER + "\n" +
            "markerFound=" + markerFound + "\n" +
            "inputCandidates=" + inputCandidates + "\n" +
            "nodeCount=" + nodes + "\n" +
            "sdk=" + Build.VERSION.SDK_INT + "\n\n";

        prefs().edit()
            .putBoolean("service_connected", true)
            .putBoolean("marker_found", markerFound)
            .putInt("input_candidates", inputCandidates)
            .putInt("node_count", nodes)
            .putLong("timestamp", System.currentTimeMillis())
            .putString("snapshot", trim(header + out))
            .apply();
    }

    private void saveEmpty(String message) {
        prefs().edit()
            .putBoolean("service_connected", true)
            .putBoolean("marker_found", false)
            .putInt("input_candidates", 0)
            .putInt("node_count", 0)
            .putLong("timestamp", System.currentTimeMillis())
            .putString("snapshot", message)
            .apply();
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    private boolean supportsAction(AccessibilityNodeInfo node, int actionId) {
        List<AccessibilityNodeInfo.AccessibilityAction> actions = node.getActionList();
        for (AccessibilityNodeInfo.AccessibilityAction action : actions) {
            if (action.getId() == actionId) {
                return true;
            }
        }
        return false;
    }

    private static void indent(StringBuilder out, int depth) {
        int count = Math.min(depth, 12);
        for (int i = 0; i < count; i++) {
            out.append("  ");
        }
    }

    private static String safe(CharSequence value) {
        if (value == null) {
            return "";
        }
        return value.toString()
            .replace("\r", "\\r")
            .replace("\n", "\\n");
    }

    private static String quote(String value) {
        return "\"" + value.replace("\"", "\\\"") + "\"";
    }

    private static String trim(String value) {
        if (value.length() <= MAX_CHARS) {
            return value;
        }
        return value.substring(0, MAX_CHARS);
    }

    private static final class NodeDepth {
        final AccessibilityNodeInfo node;
        final int depth;

        NodeDepth(AccessibilityNodeInfo node, int depth) {
            this.node = node;
            this.depth = depth;
        }
    }
}
