package com.youtube.library.collector

import android.content.Context
import java.util.UUID

data class CollectorSyncConfig(
    val serverUrl: String,
    val token: String,
    val participantId: String,
    val deviceId: String,
    val profileSlot: String,
    val autoSync: Boolean,
    val allowInsecureHttp: Boolean
) {
    fun validationError(): String? {
        if (!autoSync) return null
        if (serverUrl.isBlank()) return "Chưa cấu hình Server URL"
        if (participantId.length < 4) return "Participant ID quá ngắn"
        if (deviceId.length < 4) return "Device ID không hợp lệ"
        if (profileSlot.isBlank()) return "Profile slot đang trống"
        val normalized = serverUrl.lowercase()
        if (!normalized.startsWith("https://") && !(allowInsecureHttp && normalized.startsWith("http://"))) {
            return "Server phải dùng HTTPS (hoặc bật HTTP development)"
        }
        return null
    }
}

object CollectorSettings {
    const val PREFS = "collector_settings"
    const val KEY_DISCLOSURE_ACCEPTED = "disclosure_accepted"
    const val KEY_PAUSED = "collector_paused"
    const val KEY_SERVER_URL = "community_server_url"
    const val KEY_SERVER_TOKEN = "community_server_token"
    const val KEY_PARTICIPANT_ID = "participant_id"
    const val KEY_DEVICE_ID = "device_id"
    const val KEY_PROFILE_SLOT = "profile_slot"
    const val KEY_AUTO_SYNC = "auto_sync_enabled"
    const val KEY_ALLOW_INSECURE_HTTP = "allow_insecure_http"
    const val KEY_LAST_SYNC_AT = "last_sync_at"
    const val KEY_LAST_SYNC_ERROR = "last_sync_error"
    const val KEY_PENDING_COUNT = "pending_sync_count"

    fun ensureIdentity(context: Context): Pair<String, String> {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        var participantId = prefs.getString(KEY_PARTICIPANT_ID, null).orEmpty()
        var deviceId = prefs.getString(KEY_DEVICE_ID, null).orEmpty()
        val edit = prefs.edit()
        if (participantId.isBlank()) {
            participantId = "participant-${UUID.randomUUID()}"
            edit.putString(KEY_PARTICIPANT_ID, participantId)
        }
        if (deviceId.isBlank()) {
            deviceId = "android-${UUID.randomUUID()}"
            edit.putString(KEY_DEVICE_ID, deviceId)
        }
        if (!prefs.contains(KEY_PROFILE_SLOT)) {
            edit.putString(KEY_PROFILE_SLOT, "android-default")
        }
        edit.apply()
        return participantId to deviceId
    }

    fun load(context: Context): CollectorSyncConfig {
        ensureIdentity(context)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return CollectorSyncConfig(
            serverUrl = prefs.getString(KEY_SERVER_URL, "").orEmpty().trim().trimEnd('/'),
            token = prefs.getString(KEY_SERVER_TOKEN, "").orEmpty(),
            participantId = prefs.getString(KEY_PARTICIPANT_ID, "").orEmpty().trim(),
            deviceId = prefs.getString(KEY_DEVICE_ID, "").orEmpty().trim(),
            profileSlot = prefs.getString(KEY_PROFILE_SLOT, "android-default").orEmpty().trim(),
            autoSync = prefs.getBoolean(KEY_AUTO_SYNC, false),
            allowInsecureHttp = prefs.getBoolean(KEY_ALLOW_INSECURE_HTTP, false)
        )
    }
}
