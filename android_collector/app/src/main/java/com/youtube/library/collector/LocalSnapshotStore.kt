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

        // ADB bridge mirror. Keep it under the standard app-specific external
        // files root rather than public Downloads. If external storage is not
        // available, the canonical internal copy above remains intact.
        context.getExternalFilesDir(null)?.let { externalRoot ->
            appendLine(
                File(externalRoot, SNAPSHOT_DIR_NAME),
                "$day.jsonl",
                line
            )
        }

        prefs.edit()
            .putString("last_signature_$surface", snapshot.treeSignature)
            .putInt("count_$surface", count + 1)
            .putLong("last_capture_epoch_ms", System.currentTimeMillis())
            .putString("last_surface", surface)
            .apply()

        // Network sync is independent of collection. The snapshot is already
        // safely stored above; if upload fails AndroidAutoSync keeps it queued.
        AndroidAutoSync.enqueueSnapshot(context, snapshot)
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
