package com.nextron.mobile

import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.graphics.Color as AndroidColor
import android.os.Build
import android.os.IBinder
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import java.io.File

class BubbleService : Service() {
    companion object {
        const val START = "com.nextron.mobile.BUBBLE_START"
        const val STOP = "com.nextron.mobile.BUBBLE_STOP"
        const val HIDE = "com.nextron.mobile.BUBBLE_HIDE"
        const val RESTORE = "com.nextron.mobile.BUBBLE_RESTORE"
        const val UPLOAD = "com.nextron.mobile.BUBBLE_UPLOAD"
        const val ERROR = "com.nextron.mobile.BUBBLE_ERROR"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var manager: WindowManager
    private var bubble: View? = null
    private var panel: View? = null
    private var bubbleParams: WindowManager.LayoutParams? = null
    private var currentEvidence = ""

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        manager = getSystemService(WINDOW_SERVICE) as WindowManager
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            STOP -> { stopSelf(); return START_NOT_STICKY }
            HIDE -> { bubble?.visibility = View.GONE; panel?.visibility = View.GONE }
            RESTORE -> { bubble?.visibility = View.VISIBLE; showStatus("Capture cancelled or unavailable") }
            ERROR -> { bubble?.visibility = View.VISIBLE; showStatus(intent.getStringExtra("message") ?: "Capture failed") }
            UPLOAD -> {
                bubble?.visibility = View.VISIBLE
                val path = intent.getStringExtra("path")
                if (path != null) scope.launch { processCapture(File(path)) }
            }
            else -> startBubble()
        }
        return START_NOT_STICKY
    }

    private fun startBubble() {
        if (bubble != null) return
        if (!Settings.canDrawOverlays(this)) { stopSelf(); return }
        val channel = "nextron_bubble"
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
            NotificationChannel(channel, "Floating Investigator", NotificationManager.IMPORTANCE_LOW)
        )
        val stop = PendingIntent.getService(this, 1, Intent(this, BubbleService::class.java).setAction(STOP), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = NotificationCompat.Builder(this, channel).setSmallIcon(android.R.drawable.ic_menu_search)
            .setContentTitle("NEXTRON Floating Investigator").setContentText("Tap the bubble to request screen capture")
            .setOngoing(true).addAction(android.R.drawable.ic_delete, "Stop", stop).build()
        if (Build.VERSION.SDK_INT >= 34) startForeground(17, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        else startForeground(17, notification)

        val prefs = getSharedPreferences("nextron", Context.MODE_PRIVATE)
        val params = WindowManager.LayoutParams(64.dp, 64.dp, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS, PixelFormat.TRANSLUCENT)
        params.gravity = Gravity.TOP or Gravity.START
        params.x = prefs.getInt("bubble_x", 100.dp); params.y = prefs.getInt("bubble_y", 180.dp)
        bubbleParams = params
        val icon = TextView(this).apply {
            text = "N"; textSize = 26f; gravity = Gravity.CENTER
            contentDescription = "NEXTRON Floating Investigator: capture screen with consent"
            setTextColor(AndroidColor.rgb(88, 213, 194)); setBackgroundColor(AndroidColor.rgb(7, 16, 22))
            elevation = 10.dp.toFloat()
        }
        icon.setOnClickListener {
            startActivity(Intent(this, CaptureActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        var startX = 0; var startY = 0; var touchX = 0f; var touchY = 0f; var moved = false
        icon.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> { startX = params.x; startY = params.y; touchX = event.rawX; touchY = event.rawY; moved = false; true }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (event.rawX - touchX).toInt(); val dy = (event.rawY - touchY).toInt()
                    if (kotlin.math.abs(dx) + kotlin.math.abs(dy) > 12) moved = true
                    params.x = (startX + dx).coerceAtLeast(0); params.y = (startY + dy).coerceAtLeast(0)
                    manager.updateViewLayout(icon, params); true
                }
                MotionEvent.ACTION_UP -> {
                    prefs.edit().putInt("bubble_x", params.x).putInt("bubble_y", params.y).apply()
                    if (!moved) icon.performClick()
                    true
                }
                else -> false
            }
        }
        manager.addView(icon, params)
        bubble = icon
    }

    private val Int.dp: Int get() = (this * resources.displayMetrics.density).toInt()

    private fun showStatus(text: String, open: Boolean = false) {
        handler.post {
            panel?.let { manager.removeView(it) }; panel = null
            if (!Settings.canDrawOverlays(this)) return@post
            val box = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(14.dp, 12.dp, 14.dp, 12.dp)
                setBackgroundColor(AndroidColor.rgb(16, 29, 37))
            }
            box.addView(TextView(this).apply { this.text = text; textSize = 14f; setTextColor(AndroidColor.WHITE) })
            if (open) box.addView(Button(this).apply {
                this.text = "Open investigation"
                setOnClickListener {
                    startActivity(Intent(this@BubbleService, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                        .putExtra("evidence_id", currentEvidence))
                }
            })
            box.addView(Button(this).apply { this.text = "Dismiss"; setOnClickListener { panel?.let(manager::removeView); panel = null } })
            val p = WindowManager.LayoutParams(280.dp, WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT)
            p.gravity = Gravity.TOP or Gravity.START
            p.x = (bubbleParams?.x ?: 0) + 5.dp; p.y = (bubbleParams?.y ?: 0) + 72.dp
            manager.addView(box, p); panel = box
        }
    }

    private suspend fun processCapture(file: File) {
        try {
            val repo = NexRepository(this)
            require(repo.caseId.isNotBlank()) { "Choose an investigation in NEXTRON first" }
            showStatus("Preserving screenshot…")
            val uploaded = repo.upload(android.net.Uri.fromFile(file),
                if (file.extension.equals("mp4", true)) "SCREEN_RECORDING" else "SCREENSHOT", "SCREEN_CAPTURE")
            currentEvidence = uploaded.str("evidence_id")
            var jobId = uploaded.obj("analysis_job").str("job_id")
            if (jobId.isBlank()) jobId = repo.analyze(currentEvidence).str("job_id")
            showStatus("T-MIR job ${uploaded.obj("analysis_job").str("job_number").ifBlank { jobId }} queued", true)
            repeat(60) {
                val job = repo.job(jobId)
                val state = job.str("state")
                if (state in listOf("COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED")) {
                    val result = repo.analysis(currentEvidence)
                    val top = result.items("findings").take(3).joinToString("\n") { "${it.str("module_id")}: ${it.str("title")}" }
                    showStatus("$state\n${top.ifBlank { "No current findings; inspect module results." }}", true)
                    return
                }
                showStatus("T-MIR: $state" , true)
                delay(2500)
            }
            showStatus("Analysis still running. Open the investigation for updates.", true)
        } catch (e: Exception) { showStatus(e.message ?: "Upload or analysis failed", currentEvidence.isNotBlank()) }
        finally { file.delete() }
    }

    override fun onDestroy() {
        scope.cancel()
        panel?.let { manager.removeView(it) }; bubble?.let { manager.removeView(it) }
        super.onDestroy()
    }
}
