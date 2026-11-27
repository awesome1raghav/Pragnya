package com.nextron.mobile

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts

/** Each tap creates a fresh consent request; no projection token is cached. */
class CaptureActivity : ComponentActivity() {
    private val launcher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startService(Intent(this, BubbleService::class.java).setAction(BubbleService.HIDE))
            startForegroundService(Intent(this, CaptureService::class.java)
                .putExtra("result_code", result.resultCode).putExtra("projection_data", result.data)
                .putExtra("mode", intent.getStringExtra("mode") ?: "image"))
        } else startService(Intent(this, BubbleService::class.java).setAction(BubbleService.RESTORE))
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null) {
            val projection = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            launcher.launch(projection.createScreenCaptureIntent())
        }
    }
}
