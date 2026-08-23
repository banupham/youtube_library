package com.youtube.library.collector

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.util.concurrent.Executors

object AndroidAutoSync {
    private val executor = Executors.newSingleThreadExecutor()
    private val queueLock = Any()
    private const val QUEUE_DIR = "android_sync_queue"
    private const val QUEUE_FILE = "pending.jsonl"
    private const val MAX_PENDING = 100

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
        }

        synchronized(queueLock) {
            val rows = readPending(appContext).toMutableList()
            rows.add(envelope.toString())
            while (rows.size > MAX_PENDING) rows.removeAt(0)
            writePending(appContext, rows)
            updatePendingCount(appContext, rows.size)
        }
        flushAsync(appContext)
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
            val pending = readPending(context).toMutableList()
            if (pending.isEmpty()) {
                updatePendingCount(context, 0)
                return
            }

            var delivered = 0
            var lastError: String? = null
            for (row in pending) {
                val result = post(config, row)
                if (result.first) {
                    delivered += 1
                } else {
                    lastError = result.second ?: "Upload failed"
                    break
                }
            }

            val remaining = if (delivered >= pending.size) emptyList() else pending.drop(delivered)
            writePending(context, remaining)
            updatePendingCount(context, remaining.size)

            val prefs = context.getSharedPreferences(CollectorSettings.PREFS, Context.MODE_PRIVATE)
            if (delivered > 0) {
                prefs.edit().putString(CollectorSettings.KEY_LAST_SYNC_AT, Instant.now().toString()).apply()
            }
            if (lastError == null) {
                prefs.edit().remove(CollectorSettings.KEY_LAST_SYNC_ERROR).apply()
            } else {
                setSyncError(context, lastError)
            }
        }
    }

    private fun post(config: CollectorSyncConfig, body: String): Pair<Boolean, String?> {
        var connection: HttpURLConnection? = null
        return try {
            val endpoint = config.serverUrl.trimEnd('/') + "/v1/android/snapshot"
            connection = URL(endpoint).openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.connectTimeout = 10_000
            connection.readTimeout = 15_000
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.setRequestProperty("Accept", "application/json")
            if (config.token.isNotBlank()) {
                connection.setRequestProperty("Authorization", "Bearer ${config.token}")
            }
            val bytes = body.toByteArray(Charsets.UTF_8)
            connection.setFixedLengthStreamingMode(bytes.size)
            connection.outputStream.use { it.write(bytes) }
            val status = connection.responseCode
            if (status in 200..299) {
                true to null
            } else {
                val errorText = try {
                    connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty().take(300)
                } catch (_: Exception) {
                    ""
                }
                false to "HTTP $status${if (errorText.isNotBlank()) ": $errorText" else ""}"
            }
        } catch (error: Exception) {
            false to (error.message ?: error.javaClass.simpleName)
        } finally {
            connection?.disconnect()
        }
    }

    private fun queueFile(context: Context): File {
        val dir = File(context.filesDir, QUEUE_DIR).apply { mkdirs() }
        return File(dir, QUEUE_FILE)
    }

    private fun readPending(context: Context): List<String> {
        val file = queueFile(context)
        if (!file.exists()) return emptyList()
        return file.readLines(Charsets.UTF_8).filter { it.isNotBlank() }
    }

    private fun writePending(context: Context, rows: List<String>) {
        val file = queueFile(context)
        if (rows.isEmpty()) {
            if (file.exists()) file.writeText("", Charsets.UTF_8)
            return
        }
        file.writeText(rows.joinToString("\n", postfix = "\n"), Charsets.UTF_8)
    }

    private fun updatePendingCount(context: Context, count: Int) {
        context.getSharedPreferences(CollectorSettings.PREFS, Context.MODE_PRIVATE)
            .edit()
            .putInt(CollectorSettings.KEY_PENDING_COUNT, count)
            .apply()
    }

    private fun setSyncError(context: Context, message: String) {
        context.getSharedPreferences(CollectorSettings.PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(CollectorSettings.KEY_LAST_SYNC_ERROR, message.take(500))
            .apply()
    }
}
