package com.youtube.library.collector

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.util.UUID
import java.util.concurrent.Executors

object AndroidAutoSync {
    private val executor = Executors.newSingleThreadExecutor()
    private val queueLock = Any()
    private const val QUEUE_DIR = "android_sync_queue"
    private const val SNAPSHOT_QUEUE_FILE = "pending_snapshots.jsonl"
    private const val INTERACTION_QUEUE_FILE = "pending_interactions.jsonl"
    private const val MAX_PENDING = 200

    fun enqueueSnapshot(context: Context, snapshot: AccessibilitySnapshot) {
        val appContext = context.applicationContext
        val config = CollectorSettings.load(appContext)
        if (!config.autoSync) return
        val envelope = JSONObject().apply {
            put("schema_version", "1.0.0")
            put("participant_id", config.participantId)
            put("device_id", config.deviceId)
            put("profile_slot", config.profileSlot)
            put("sent_at", Instant.now().toString())
            put("snapshot", snapshot.toJson())
        }.toString()
        enqueue(appContext, SNAPSHOT_QUEUE_FILE, envelope)
    }

    fun enqueueInteraction(
        context: Context,
        eventType: String,
        score: Double,
        confidence: Double,
        surface: String?,
        treeSignature: String?,
        eventClass: String? = null
    ) {
        val appContext = context.applicationContext
        val config = CollectorSettings.load(appContext)
        if (!config.autoSync) return
        val profileId = "android:${config.deviceId}:${config.profileSlot}"
        val event = JSONObject().apply {
            put("schema_version", "1.0.0")
            put("event_id", "evt-${UUID.randomUUID()}")
            put("participant_id", config.participantId)
            put("device_id", config.deviceId)
            put("profile_id", profileId)
            put("profile_slot", config.profileSlot)
            put("platform", "android")
            put("captured_at", Instant.now().toString())
            put("event_type", eventType)
            put("engagement_score", score)
            put("score_model", "natural_interaction_v1")
            put("source", "natural_user_action")
            put("video_id", JSONObject.NULL)
            put("video_title", JSONObject.NULL)
            put("channel", JSONObject.NULL)
            put("channel_subscription_state", "unknown")
            put("surface", surface ?: JSONObject.NULL)
            put("confidence", confidence)
            put("context", JSONObject().apply {
                put("tree_signature", treeSignature ?: JSONObject.NULL)
                put("event_class", eventClass ?: JSONObject.NULL)
                put("detection", "android_accessibility_event")
            })
        }.toString()
        enqueue(appContext, INTERACTION_QUEUE_FILE, event)
    }

    private fun enqueue(context: Context, fileName: String, row: String) {
        executor.execute {
            synchronized(queueLock) {
                val rows = readPending(context, fileName).toMutableList()
                rows.add(row)
                while (rows.size > MAX_PENDING) rows.removeAt(0)
                writePending(context, fileName, rows)
                updatePendingCount(context)
            }
            flush(context)
        }
    }

    fun flushAsync(context: Context) {
        val appContext = context.applicationContext
        executor.execute { flush(appContext) }
    }

    private fun flush(context: Context) {
        val config = CollectorSettings.load(context)
        if (!config.autoSync) return
        val validationError = config.validationError()
        if (validationError != null) {
            setSyncError(context, validationError)
            return
        }
        synchronized(queueLock) {
            val snapshotError = flushQueue(context, config, SNAPSHOT_QUEUE_FILE, "/v1/android/snapshot")
            val interactionError = flushQueue(context, config, INTERACTION_QUEUE_FILE, "/v1/interaction")
            updatePendingCount(context)
            val error = snapshotError ?: interactionError
            val prefs = context.getSharedPreferences(CollectorSettings.PREFS, Context.MODE_PRIVATE)
            if (error == null) {
                prefs.edit()
                    .putString(CollectorSettings.KEY_LAST_SYNC_AT, Instant.now().toString())
                    .remove(CollectorSettings.KEY_LAST_SYNC_ERROR)
                    .apply()
            } else {
                setSyncError(context, error)
            }
        }
    }

    private fun flushQueue(
        context: Context,
        config: CollectorSyncConfig,
        fileName: String,
        endpoint: String
    ): String? {
        val pending = readPending(context, fileName).toMutableList()
        if (pending.isEmpty()) return null
        var delivered = 0
        var lastError: String? = null
        for (row in pending) {
            val result = post(config, endpoint, row)
            if (result.first) delivered += 1 else {
                lastError = result.second ?: "Upload failed"
                break
            }
        }
        val remaining = if (delivered >= pending.size) emptyList() else pending.drop(delivered)
        writePending(context, fileName, remaining)
        return lastError
    }

    private fun post(config: CollectorSyncConfig, endpointPath: String, body: String): Pair<Boolean, String?> {
        var connection: HttpURLConnection? = null
        return try {
            connection = URL(config.serverUrl.trimEnd('/') + endpointPath).openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.connectTimeout = 10_000
            connection.readTimeout = 15_000
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.setRequestProperty("Accept", "application/json")
            if (config.token.isNotBlank()) connection.setRequestProperty("Authorization", "Bearer ${config.token}")
            val bytes = body.toByteArray(Charsets.UTF_8)
            connection.setFixedLengthStreamingMode(bytes.size)
            connection.outputStream.use { it.write(bytes) }
            val status = connection.responseCode
            if (status in 200..299) true to null else {
                val errorText = try {
                    connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty().take(300)
                } catch (_: Exception) { "" }
                false to "HTTP $status${if (errorText.isNotBlank()) ": $errorText" else ""}"
            }
        } catch (error: Exception) {
            false to (error.message ?: error.javaClass.simpleName)
        } finally {
            connection?.disconnect()
        }
    }

    private fun queueFile(context: Context, fileName: String): File {
        val dir = File(context.filesDir, QUEUE_DIR).apply { mkdirs() }
        return File(dir, fileName)
    }
    private fun readPending(context: Context, fileName: String): List<String> {
        val file = queueFile(context, fileName)
        if (!file.exists()) return emptyList()
        return file.readLines(Charsets.UTF_8).filter { it.isNotBlank() }
    }
    private fun writePending(context: Context, fileName: String, rows: List<String>) {
        val file = queueFile(context, fileName)
        if (rows.isEmpty()) {
            if (file.exists()) file.writeText("", Charsets.UTF_8)
        } else {
            file.writeText(rows.joinToString("\n", postfix = "\n"), Charsets.UTF_8)
        }
    }
    private fun updatePendingCount(context: Context) {
        val count = readPending(context, SNAPSHOT_QUEUE_FILE).size + readPending(context, INTERACTION_QUEUE_FILE).size
        context.getSharedPreferences(CollectorSettings.PREFS, Context.MODE_PRIVATE)
            .edit().putInt(CollectorSettings.KEY_PENDING_COUNT, count).apply()
    }
    private fun setSyncError(context: Context, message: String) {
        context.getSharedPreferences(CollectorSettings.PREFS, Context.MODE_PRIVATE)
            .edit().putString(CollectorSettings.KEY_LAST_SYNC_ERROR, message.take(500)).apply()
    }
}
