package com.echonet.triage

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.echonet.triage.audio.UltrasonicListenerService

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║       RESONANCE-PROTOCOL  ·  MAIN ACTIVITY (Minimal)           ║
 * ║   Phase 3: Permission grants → Start listener service           ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * This is a bare-bones launcher that:
 *   1. Requests RECORD_AUDIO + POST_NOTIFICATIONS permissions
 *   2. Starts UltrasonicListenerService as a foreground service
 *   3. Logs decoded messages from the broadcast receiver
 *
 * Full UI comes in Phase 4.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "MainActivity"
        private const val REQUEST_PERMISSIONS = 100
    }

    // ── Broadcast receiver for decoded messages ─────────────────────
    private val messageReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                UltrasonicListenerService.ACTION_MESSAGE_DECODED -> {
                    val text = intent.getStringExtra(
                        UltrasonicListenerService.EXTRA_DECODED_TEXT
                    ) ?: return

                    Log.i(TAG, "🔔 Received decoded message: \"$text\"")
                    Toast.makeText(
                        context,
                        "📡 Received: \"$text\"",
                        Toast.LENGTH_LONG
                    ).show()
                }

                UltrasonicListenerService.ACTION_STATE_CHANGED -> {
                    val state = intent.getStringExtra(
                        UltrasonicListenerService.EXTRA_STATE
                    ) ?: return
                    Log.d(TAG, "Decoder state → $state")
                }
            }
        }
    }

    // ═════════════════════════════════════════════════════════════════
    //  LIFECYCLE
    // ═════════════════════════════════════════════════════════════════

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        Log.i(TAG, """
            |╔══════════════════════════════════════════════════════════╗
            |║          ECHONET-TRIAGE · Phase 3                       ║
            |║          Mobile Node Initialization                     ║
            |╚══════════════════════════════════════════════════════════╝
        """.trimMargin())

        // Phase 3: No custom UI — just request permissions and start listening
        requestRequiredPermissions()
    }

    override fun onResume() {
        super.onResume()

        // Register broadcast receivers
        val filter = IntentFilter().apply {
            addAction(UltrasonicListenerService.ACTION_MESSAGE_DECODED)
            addAction(UltrasonicListenerService.ACTION_STATE_CHANGED)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(messageReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(messageReceiver, filter)
        }
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(messageReceiver)
    }

    // ═════════════════════════════════════════════════════════════════
    //  PERMISSIONS
    // ═════════════════════════════════════════════════════════════════

    private fun requestRequiredPermissions() {
        val needed = mutableListOf<String>()

        // Microphone — always required
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            needed.add(Manifest.permission.RECORD_AUDIO)
        }

        // Notifications — required on Android 13+ for foreground service notification
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                needed.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (needed.isEmpty()) {
            // All permissions already granted — start listening
            startListenerService()
        } else {
            ActivityCompat.requestPermissions(
                this,
                needed.toTypedArray(),
                REQUEST_PERMISSIONS
            )
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        if (requestCode != REQUEST_PERMISSIONS) return

        val audioGranted = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        if (audioGranted) {
            startListenerService()
        } else {
            Log.e(TAG, "❌ RECORD_AUDIO permission denied — cannot listen")
            Toast.makeText(
                this,
                "⚠ Microphone permission is required for EchoNet mesh",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    // ═════════════════════════════════════════════════════════════════
    //  SERVICE CONTROL
    // ═════════════════════════════════════════════════════════════════

    private fun startListenerService() {
        Log.i(TAG, "▶ Starting UltrasonicListenerService …")
        val intent = Intent(this, UltrasonicListenerService::class.java)
        ContextCompat.startForegroundService(this, intent)
        Toast.makeText(this, "📡 Listening for ultrasonic signals …", Toast.LENGTH_SHORT).show()
    }
}
