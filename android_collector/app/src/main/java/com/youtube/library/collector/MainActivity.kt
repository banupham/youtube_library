package com.youtube.library.collector

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.time.LocalDate

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(36, 48, 36, 48)
        }

        val title = TextView(this).apply {
            text = "YouTube Library Android Collector"
            textSize = 22f
        }
        val disclosure = TextView(this).apply {
            text = "Ứng dụng dùng Android AccessibilityService để đọc cây AccessibilityNodeInfo CHỈ khi ứng dụng YouTube (com.google.android.youtube) đang mở. Dữ liệu dùng để suy ra recommendation/profile evidence cho cộng đồng nghiên cứu. Collector không click, không gesture, không play/like/comment/subscribe và không đọc ứng dụng khác. Snapshot node tree được lưu local ở bản v1."
            textSize = 15f
            setPadding(0, 28, 0, 28)
        }
        val status = TextView(this).apply {
            textSize = 14f
            text = if (prefs.getBoolean(KEY_PAUSED, false)) {
                "Trạng thái collector: TẠM DỪNG"
            } else {
                "Trạng thái collector: SẴN SÀNG — tự chạy khi YouTube mở sau khi quyền trợ năng được bật"
            }
        }

        val enableButton = Button(this).apply {
            text = "Tôi đồng ý & mở Cài đặt trợ năng"
            setOnClickListener {
                prefs.edit().putBoolean(KEY_DISCLOSURE_ACCEPTED, true).putBoolean(KEY_PAUSED, false).apply()
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }

        val pauseButton = Button(this).apply {
            text = if (prefs.getBoolean(KEY_PAUSED, false)) "Tiếp tục thu thập" else "Tạm dừng thu thập"
            setOnClickListener {
                val paused = !prefs.getBoolean(KEY_PAUSED, false)
                prefs.edit().putBoolean(KEY_PAUSED, paused).apply()
                text = if (paused) "Tiếp tục thu thập" else "Tạm dừng thu thập"
                status.text = if (paused) {
                    "Trạng thái collector: TẠM DỪNG"
                } else {
                    "Trạng thái collector: SẴN SÀNG — tự chạy khi YouTube mở"
                }
            }
        }

        val exportButton = Button(this).apply {
            text = "Xuất snapshot JSONL hôm nay"
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

        root.addView(title)
        root.addView(disclosure)
        root.addView(status)
        root.addView(enableButton)
        root.addView(pauseButton)
        root.addView(exportButton)
        setContentView(root)
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
        File(filesDir, "youtube_accessibility_snapshots"),
        "${LocalDate.now()}.jsonl"
    )

    companion object {
        const val PREFS = "collector_settings"
        const val KEY_DISCLOSURE_ACCEPTED = "disclosure_accepted"
        const val KEY_PAUSED = "collector_paused"
        private const val REQUEST_EXPORT = 7001
    }
}
