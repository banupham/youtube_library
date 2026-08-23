package com.youtube.library.collector

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.time.LocalDate

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        CollectorSettings.ensureIdentity(this)
        val prefs = getSharedPreferences(CollectorSettings.PREFS, MODE_PRIVATE)
        val current = CollectorSettings.load(this)

        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(36, 48, 36, 48)
        }
        val scroll = ScrollView(this).apply { addView(body) }

        val title = TextView(this).apply {
            text = "YouTube Library Android Collector"
            textSize = 22f
        }
        val disclosure = TextView(this).apply {
            text = "Ứng dụng dùng Android AccessibilityService để đọc cây AccessibilityNodeInfo CHỈ khi ứng dụng YouTube (com.google.android.youtube) đang mở. Khi Auto sync được cấu hình, snapshot YouTube hợp lệ sẽ tự gửi tới community server của dự án. Collector không click, không gesture, không play/like/comment/subscribe và không đọc ứng dụng khác."
            textSize = 15f
            setPadding(0, 28, 0, 28)
        }
        val collectorStatus = TextView(this).apply {
            textSize = 14f
            text = if (prefs.getBoolean(CollectorSettings.KEY_PAUSED, false)) {
                "Collector: TẠM DỪNG"
            } else {
                "Collector: SẴN SÀNG — tự chạy khi YouTube mở sau khi quyền trợ năng được bật"
            }
        }
        val syncStatus = TextView(this).apply {
            textSize = 13f
            setPadding(0, 12, 0, 18)
            text = buildSyncStatus()
        }

        val enableButton = Button(this).apply {
            text = "Tôi đồng ý & mở Cài đặt trợ năng"
            setOnClickListener {
                prefs.edit()
                    .putBoolean(CollectorSettings.KEY_DISCLOSURE_ACCEPTED, true)
                    .putBoolean(CollectorSettings.KEY_PAUSED, false)
                    .apply()
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }

        val pauseButton = Button(this).apply {
            text = if (prefs.getBoolean(CollectorSettings.KEY_PAUSED, false)) "Tiếp tục thu thập" else "Tạm dừng thu thập"
            setOnClickListener {
                val paused = !prefs.getBoolean(CollectorSettings.KEY_PAUSED, false)
                prefs.edit().putBoolean(CollectorSettings.KEY_PAUSED, paused).apply()
                text = if (paused) "Tiếp tục thu thập" else "Tạm dừng thu thập"
                collectorStatus.text = if (paused) {
                    "Collector: TẠM DỪNG"
                } else {
                    "Collector: SẴN SÀNG — tự chạy khi YouTube mở"
                }
            }
        }

        val settingsTitle = TextView(this).apply {
            text = "\nCommunity server / Auto sync"
            textSize = 18f
        }
        val settingsHint = TextView(this).apply {
            text = "Cấu hình một lần. Sau đó mỗi snapshot hợp lệ được lưu local trước rồi tự xếp hàng upload. Nếu mất mạng/server lỗi, queue local giữ lại để retry. HTTPS được yêu cầu cho server thật."
            textSize = 13f
        }

        val serverUrl = EditText(this).apply {
            hint = "https://community.example.com"
            setText(current.serverUrl)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        val token = EditText(this).apply {
            hint = "Project token"
            setText(current.token)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val participantId = EditText(this).apply {
            hint = "Participant ID / community member code"
            setText(current.participantId)
            inputType = InputType.TYPE_CLASS_TEXT
        }
        val profileSlot = EditText(this).apply {
            hint = "Profile slot, ví dụ android-main"
            setText(current.profileSlot)
            inputType = InputType.TYPE_CLASS_TEXT
        }
        val deviceId = TextView(this).apply {
            text = "Device ID: ${current.deviceId}"
            textSize = 12f
        }
        val autoSync = CheckBox(this).apply {
            text = "Tự động gửi snapshot lên server"
            isChecked = if (prefs.contains(CollectorSettings.KEY_AUTO_SYNC)) current.autoSync else true
        }
        val allowHttp = CheckBox(this).apply {
            text = "Cho phép HTTP không mã hóa (chỉ development/LAN test)"
            isChecked = current.allowInsecureHttp
        }

        val saveButton = Button(this).apply {
            text = "Lưu cấu hình & chạy Auto sync"
            setOnClickListener {
                prefs.edit()
                    .putString(CollectorSettings.KEY_SERVER_URL, serverUrl.text.toString().trim().trimEnd('/'))
                    .putString(CollectorSettings.KEY_SERVER_TOKEN, token.text.toString())
                    .putString(CollectorSettings.KEY_PARTICIPANT_ID, participantId.text.toString().trim())
                    .putString(CollectorSettings.KEY_PROFILE_SLOT, profileSlot.text.toString().trim())
                    .putBoolean(CollectorSettings.KEY_AUTO_SYNC, autoSync.isChecked)
                    .putBoolean(CollectorSettings.KEY_ALLOW_INSECURE_HTTP, allowHttp.isChecked)
                    .apply()

                val saved = CollectorSettings.load(this@MainActivity)
                val error = saved.validationError()
                if (error != null) {
                    Toast.makeText(this@MainActivity, error, Toast.LENGTH_LONG).show()
                } else {
                    AndroidAutoSync.flushAsync(this@MainActivity)
                    Toast.makeText(
                        this@MainActivity,
                        if (saved.autoSync) "Đã lưu. Auto sync đang bật." else "Đã lưu. Auto sync đang tắt.",
                        Toast.LENGTH_SHORT
                    ).show()
                }
                syncStatus.text = buildSyncStatus()
            }
        }

        val exportButton = Button(this).apply {
            text = "Xuất snapshot JSONL hôm nay (fallback)"
            setOnClickListener {
                val source = todaySnapshotFile()
                if (!source.exists() || source.length() == 0L) {
                    Toast.makeText(this@MainActivity, "Hôm nay chưa có snapshot để xuất.", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
                val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "application/x-ndjson"
                    putExtra(Intent.EXTRA_TITLE, "youtube_accessibility_${LocalDate.now()}.jsonl")
                }
                startActivityForResult(intent, REQUEST_EXPORT)
            }
        }

        body.addView(title)
        body.addView(disclosure)
        body.addView(collectorStatus)
        body.addView(syncStatus)
        body.addView(enableButton)
        body.addView(pauseButton)
        body.addView(settingsTitle)
        body.addView(settingsHint)
        body.addView(serverUrl)
        body.addView(token)
        body.addView(participantId)
        body.addView(profileSlot)
        body.addView(deviceId)
        body.addView(autoSync)
        body.addView(allowHttp)
        body.addView(saveButton)
        body.addView(exportButton)
        setContentView(scroll)

        AndroidAutoSync.flushAsync(this)
    }

    private fun buildSyncStatus(): String {
        val prefs = getSharedPreferences(CollectorSettings.PREFS, MODE_PRIVATE)
        val pending = prefs.getInt(CollectorSettings.KEY_PENDING_COUNT, 0)
        val lastSync = prefs.getString(CollectorSettings.KEY_LAST_SYNC_AT, null)
        val error = prefs.getString(CollectorSettings.KEY_LAST_SYNC_ERROR, null)
        return buildString {
            append("Auto sync pending: ").append(pending)
            if (!lastSync.isNullOrBlank()) append(" · last: ").append(lastSync)
            if (!error.isNullOrBlank()) append("\nLast sync error: ").append(error)
        }
    }

    @Deprecated("Legacy Activity result API is sufficient for the dependency-free prototype")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_EXPORT || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        val source = todaySnapshotFile()
        try {
            contentResolver.openOutputStream(uri, "w")?.use { output ->
                source.inputStream().use { input -> input.copyTo(output) }
            } ?: error("Không mở được file đích")
            Toast.makeText(this, "Đã xuất snapshot JSONL.", Toast.LENGTH_SHORT).show()
        } catch (error: Exception) {
            Toast.makeText(this, "Xuất snapshot lỗi: ${error.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun todaySnapshotFile(): File = File(
        File(filesDir, LocalSnapshotStore.SNAPSHOT_DIR_NAME),
        "${LocalDate.now()}.jsonl"
    )

    companion object {
        private const val REQUEST_EXPORT = 7001
    }
}
