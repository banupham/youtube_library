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

        val dir = File(context.filesDir, "youtube_accessibility_snapshots").apply { mkdirs() }
        val file = File(dir, "$day.jsonl")
        file.appendText(snapshot.toJson().toString() + "\n", Charsets.UTF_8)

        prefs.edit()
            .putString("last_signature_$surface", snapshot.treeSignature)
            .putInt("count_$surface", count + 1)
            .putLong("last_capture_epoch_ms", System.currentTimeMillis())
            .putString("last_surface", surface)
            .apply()
        return true
    }

    companion object {
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
