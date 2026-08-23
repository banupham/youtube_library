package com.youtube.library.collector

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo
import java.security.MessageDigest

object NodeTreeExtractor {
    private const val MAX_NODES = 450
    private const val MAX_DEPTH = 18
    private const val MAX_TEXT = 200
    private const val MAX_DESCRIPTION = 320
    private const val MAX_VIEW_ID = 180

    fun extract(root: AccessibilityNodeInfo): Pair<List<NodeRecord>, String> {
        val output = ArrayList<NodeRecord>(MAX_NODES)
        val queue = ArrayDeque<Pair<AccessibilityNodeInfo, Int>>()
        queue.add(root to 0)

        while (queue.isNotEmpty() && output.size < MAX_NODES) {
            val (node, depth) = queue.removeFirst()
            if (depth > MAX_DEPTH) continue

            val packageName = node.packageName?.toString().orEmpty()
            if (packageName.isNotEmpty() && packageName != YouTubeAccessibilityService.YOUTUBE_PACKAGE) {
                continue
            }

            val text = clean(node.text?.toString(), MAX_TEXT)
            val description = clean(node.contentDescription?.toString(), MAX_DESCRIPTION)
            val viewId = clean(node.viewIdResourceName, MAX_VIEW_ID)
            val shouldKeep = text != null || description != null || viewId != null || node.isSelected || node.isScrollable

            if (shouldKeep) {
                val bounds = Rect()
                node.getBoundsInScreen(bounds)
                output.add(
                    NodeRecord(
                        depth = depth,
                        text = text,
                        contentDescription = description,
                        viewId = viewId,
                        className = clean(node.className?.toString(), 160) ?: "",
                        clickable = node.isClickable,
                        selected = node.isSelected,
                        scrollable = node.isScrollable,
                        childCount = node.childCount,
                        left = bounds.left,
                        top = bounds.top,
                        right = bounds.right,
                        bottom = bounds.bottom
                    )
                )
            }

            if (depth < MAX_DEPTH) {
                for (index in 0 until node.childCount) {
                    val child = node.getChild(index) ?: continue
                    queue.add(child to depth + 1)
                }
            }
        }

        return output to signature(output)
    }

    private fun clean(value: String?, limit: Int): String? {
        val normalized = value
            ?.replace(Regex("\\s+"), " ")
            ?.trim()
            ?.take(limit)
            .orEmpty()
        return normalized.ifEmpty { null }
    }

    private fun signature(nodes: List<NodeRecord>): String {
        val canonical = buildString {
            nodes.forEach { node ->
                append(node.depth).append('|')
                append(node.viewId.orEmpty()).append('|')
                append(node.text.orEmpty()).append('|')
                append(node.contentDescription.orEmpty()).append('|')
                append(node.selected).append(';')
            }
        }
        return MessageDigest.getInstance("SHA-256")
            .digest(canonical.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
            .take(32)
    }
}
