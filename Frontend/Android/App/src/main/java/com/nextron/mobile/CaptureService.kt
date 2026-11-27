@file:Suppress("DEPRECATION")
package com.nextron.mobile

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.MediaRecorder
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import java.io.File

class CaptureService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val channel = "nextron_capture"
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
            NotificationChannel(channel, "Screen capture", NotificationManager.IMPORTANCE_LOW))
        val notification = NotificationCompat.Builder(this, channel).setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle("NEXTRON screen capture").setContentText("Capturing one user-authorized screenshot").build()
        if (Build.VERSION.SDK_INT >= 34) startForeground(18, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        else startForeground(18, notification)
        val code = intent?.getIntExtra("result_code", Activity.RESULT_CANCELED) ?: Activity.RESULT_CANCELED
        @Suppress("DEPRECATION") val data = intent?.getParcelableExtra<Intent>("projection_data")
        if (code != Activity.RESULT_OK || data == null) { reportError("Screen capture consent expired"); return START_NOT_STICKY }
        scope.launch { capture(code, data, intent.getStringExtra("mode") == "record") }
        return START_NOT_STICKY
    }

    private suspend fun capture(code: Int, data: Intent, record: Boolean) {
        var projection: MediaProjection? = null
        var display: VirtualDisplay? = null
        var reader: ImageReader? = null
        val thread = HandlerThread("nextron-screen").apply { start() }
        try {
            delay(450) // allow the overlay and consent activity to leave the captured display
            val metrics = resources.displayMetrics
            val width = metrics.widthPixels; val height = metrics.heightPixels
            val ready = CompletableDeferred<Bitmap>()
            projection = (getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager).getMediaProjection(code, data)
            projection.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() { if (!ready.isCompleted) ready.completeExceptionally(IllegalStateException("Capture session ended")) }
            }, Handler(thread.looper))
            val file: File
            if (record) {
                val video = File.createTempFile("nextron-capture-", ".mp4", cacheDir)
                val recorder = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this) else MediaRecorder()
                try {
                    val scale = minOf(1.0, 1280.0 / maxOf(width, height))
                    val w = ((width * scale).toInt() / 2) * 2; val h = ((height * scale).toInt() / 2) * 2
                    recorder.setVideoSource(MediaRecorder.VideoSource.SURFACE)
                    recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                    recorder.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
                    recorder.setVideoSize(w, h)
                    recorder.setVideoFrameRate(20)
                    recorder.setVideoEncodingBitRate(2_500_000)
                    recorder.setOutputFile(video.absolutePath)
                    recorder.prepare()
                    display = projection.createVirtualDisplay("NEXTRON recording", w, h, metrics.densityDpi,
                        DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, recorder.surface, null, Handler(thread.looper))
                    recorder.start()
                    delay(15_000)
                    recorder.stop()
                    file = video
                } catch (e: Exception) { video.delete(); throw e }
                finally { recorder.release() }
            } else {
                reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
                reader.setOnImageAvailableListener({ source ->
                    val image = source.acquireLatestImage() ?: return@setOnImageAvailableListener
                    try {
                        val plane = image.planes[0]
                        val padded = width + (plane.rowStride - plane.pixelStride * width) / plane.pixelStride
                        val bitmap = Bitmap.createBitmap(padded, height, Bitmap.Config.ARGB_8888)
                        bitmap.copyPixelsFromBuffer(plane.buffer)
                        val cropped = Bitmap.createBitmap(bitmap, 0, 0, width, height)
                        bitmap.recycle()
                        ready.complete(cropped)
                    } catch (e: Exception) { ready.completeExceptionally(e) }
                    finally { image.close() }
                }, Handler(thread.looper))
                display = projection.createVirtualDisplay("NEXTRON capture", width, height, metrics.densityDpi,
                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader.surface, null, Handler(thread.looper))
                val bitmap = withTimeout(8000) { ready.await() }
                val visible = (0 until 8).any { y -> (0 until 8).any { x ->
                    val pixel = bitmap.getPixel((x * width / 8).coerceAtMost(width - 1), (y * height / 8).coerceAtMost(height - 1))
                    (pixel and 0x00FFFFFF) != 0
                } }
                if (!visible) { bitmap.recycle(); error("Capture contains no visible pixels; the screen may be protected") }
                file = File.createTempFile("nextron-capture-", ".png", cacheDir)
                withContext(Dispatchers.IO) { file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) } }
                bitmap.recycle()
            }
            startService(Intent(this, BubbleService::class.java).setAction(BubbleService.UPLOAD).putExtra("path", file.absolutePath))
        } catch (e: Exception) { reportError(e.message ?: "Screen capture failed or was protected") }
        finally {
            display?.release(); reader?.close(); projection?.stop(); thread.quitSafely()
            stopForeground(STOP_FOREGROUND_REMOVE); stopSelf()
        }
    }

    private fun reportError(reason: String) {
        startService(Intent(this, BubbleService::class.java).setAction(BubbleService.ERROR).putExtra("message", reason))
        stopSelf()
    }

    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
