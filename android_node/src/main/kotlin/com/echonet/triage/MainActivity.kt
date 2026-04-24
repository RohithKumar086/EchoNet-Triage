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
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.echonet.triage.audio.FskEncoder
import com.echonet.triage.audio.UltrasonicBroadcaster
import com.echonet.triage.audio.UltrasonicListenerService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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

    private lateinit var tvLog: TextView
    private lateinit var etCustomMessage: EditText
    private val broadcaster = UltrasonicBroadcaster()

    // ── Broadcast receiver for decoded messages ─────────────────────
    private val messageReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                UltrasonicListenerService.ACTION_MESSAGE_DECODED -> {
                    val text = intent.getStringExtra(
                        UltrasonicListenerService.EXTRA_DECODED_TEXT
                    ) ?: return

                    Log.i(TAG, "🔔 Received decoded message: \"$text\"")
                    appendLog("📡 Received: \"$text\"")
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
                    // appendLog("Decoder state → $state") // Optional: uncomment if you want chatty state logs
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
        setContentView(R.layout.activity_main)

        Log.i(TAG, """
            |╔══════════════════════════════════════════════════════════╗
            |║          ECHONET-TRIAGE · Phase 4                       ║
            |║          Mobile Node Transmitter                        ║
            |╚══════════════════════════════════════════════════════════╝
        """.trimMargin())

        setupUI()
        requestRequiredPermissions()
    }

    private fun setupUI() {
        tvLog = findViewById(R.id.tvLog)
        etCustomMessage = findViewById(R.id.etCustomMessage)

        findViewById<Button>(R.id.btnSendSos).setOnClickListener {
            transmitMessage("SOS!")
        }

        findViewById<Button>(R.id.btnSendCustom).setOnClickListener {
            val msg = etCustomMessage.text.toString().trim()
            if (msg.isNotEmpty()) {
                transmitMessage(msg)
                etCustomMessage.text.clear()
            } else {
                Toast.makeText(this, "Please enter a message", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun transmitMessage(message: String) {
        val cleanMsg = message.take(16).uppercase() // enforce max 16 chars as per config
        appendLog("▶ Transmitting: \"$cleanMsg\" ...")
        
        lifecycleScope.launch(Dispatchers.Default) {
            try {
                // 1. Encode text to PCM audio array
                val pcm16 = FskEncoder.encodeFsk(cleanMsg)
                
                // 2. Play audio using AudioTrack
                broadcaster.broadcast(pcm16)
                
                withContext(Dispatchers.Main) {
                    appendLog("✅ Broadcast complete: \"$cleanMsg\"")
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    appendLog("❌ Broadcast failed: ${e.message}")
                }
            }
        }
    }

    private fun appendLog(line: String) {
        val current = tvLog.text.toString()
        tvLog.text = "$current\n$line"
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
