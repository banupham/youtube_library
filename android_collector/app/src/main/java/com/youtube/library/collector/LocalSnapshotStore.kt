package com.youtube.library.collector

import android.content.Context
import java.io.File
import java.time.LocalDate

class LocalSnapshotStore(private val context: Context) {
    private val prefs = context.getSharedPreferences("snapshot_quota", Context.MODE_PRIVATE)

    fun appendIfAllowed(snapshot: AccessibilitySnapshot): Boolean {
        val surface = snapshot.surfaceGuess.surface
        val day = LocalDate.now().toString()
        val storedDay = prefs.getString("quota_day", null)
        if (storedDay != day) {
            prefs.edit().clear().putString("quota_day", day).apply()
        }

        val lastSignature = prefs.getString("last_signature_$surface", null)
        if (lastSignature == snapshot.treeSignature) return false

        val count = prefs.getInt("count_$surface", 0)
        val cap = DAILY_CAPS[surface] ?: DAILY_CAPS.getValue("unknown")
        if (count >= cap) return false

        val line = snapshot.toJson().toString() + "\n"

        // Canonical private copy used by the app/export flow.
        appendLine(
            File(context.filesDir, SNAPSHOT_DIR_NAME),
            "$day.jsonl",
            line
        )

        // ADB bridge mirror. This remains app-specific external storage rather than
        // public Downloads, so participants do not need to copy/export files by hand.
        // If external storage is unavailable, collection still succeeds using the
        // canonical internal copy and the PC bridge can try run-as as a debug fallback.
        context.getExternalFilesDir(SNAPSHOT_DIR_NAME)?.let { externalDir ->
            appendLine(externalDir, "$day.jsonl", line)
        }

        prefs.edit()
            .putString("last_signature_$surface", snapshot.treeSignature)
            .putInt("count_$surface", count + 1)
            .putLong("last_capture_epoch_ms", System.currentTimeMillis())
            .putString("last_surface", surface)
            .apply()
        return true
    }

    private fun appendLine(dir: File, fileName: String, line: String) {
        dir.mkdirs()
        File(dir, fileName).appendText(line, Charsets.UTF_8)
    }

    companion object {
        const val SNAPSHOT_DIR_NAME = "youtube_accessibility_snapshots"

        val DAILY_CAPS = mapOf(
            "home" to 4,
            "watch" to 24,
            "subscriptions" to 4,
            "shorts" to 12,
            "search" to 8,
            "unknown" to 6
        )
    }
}
