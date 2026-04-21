package com.echonet.triage.audio

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║       RESONANCE-PROTOCOL  ·  ULTRASONIC LISTENER SERVICE        ║
 * ║    Foreground service: AudioRecord → Goertzel → FSK Decoder     ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * Lifecycle:
 *   1. Started as a foreground service (sticky notification)
 *   2. Acquires a partial wake lock to keep CPU alive while screen is off
 *   3. Opens AudioRecord at 44100 Hz / MONO / PCM_16BIT
 *   4. Reads STEP_SIZE samples per iteration in a coroutine loop
 *   5. Runs GoertzelDetector.decideBit() on each window
 *   6. Feeds decisions into FskDecoder (streaming state machine)
 *   7. Broadcasts decoded messages via LocalBroadcast
 *
 * Start from Activity:
 *   val intent = Intent(this, UltrasonicListenerService::class.java)
 *   ContextCompat.startForegroundService(this, intent)
 *
 * Stop:
 *   stopService(Intent(this, UltrasonicListenerService::class.java))
 */
class UltrasonicListenerService : Service() {

    companion object {
        private const val TAG = "UltrasonicListener"

        // Notification
        private const val CHANNEL_ID = "echonet_listener_channel"
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_NAME = "EchoNet Listener"

        // Broadcast action for decoded messages
        const val ACTION_MESSAGE_DECODED = "com.echonet.triage.MESSAGE_DECODED"
        const val EXTRA_DECODED_TEXT = "decoded_text"

        // Broadcast action for state changes
        const val ACTION_STATE_CHANGED = "com.echonet.triage.STATE_CHANGED"
        const val EXTRA_STATE = "decoder_state"
    }

    // ── Coroutine scope tied to service lifecycle ────────────────────
    private val serviceScope = CoroutineScope(
        SupervisorJob() + Dispatchers.Default
    )

    // ── Audio components ────────────────────────────────────────────
    private var audioRecord: AudioRecord? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var isListening = false

    // ── FSK Decoder ─────────────────────────────────────────────────
    private lateinit var fskDecoder: FskDecoder

    // ═════════════════════════════════════════════════════════════════
    //  SERVICE LIFECYCLE
    // ═════════════════════════════════════════════════════════════════

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "🔧 Service created")

        // Initialise the streaming decoder with callbacks
        fskDecoder = FskDecoder(
            onMessageDecoded = { text -> broadcastMessage(text) },
            onStatusChanged = { state -> broadcastState(state) }
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "▶ Service starting — entering foreground")

        // Must call startForeground() within 5 seconds of startForegroundService()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification("Scanning for signals…"))

        // Acquire wake lock
        acquireWakeLock()

        // Begin audio capture
        startListening()

        // If the system kills us, restart automatically
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "⏹ Service destroyed — stopping listener")
        stopListening()
        releaseWakeLock()
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null  // not a bound service

    // ═════════════════════════════════════════════════════════════════
    //  AUDIO RECORD INITIALISATION
    // ═════════════════════════════════════════════════════════════════

    private fun initAudioRecord(): AudioRecord? {
        val sampleRate = ResonanceConfig.SAMPLE_RATE
        val channelConfig = AudioFormat.CHANNEL_IN_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT

        // Calculate minimum buffer size
        val minBufferBytes = AudioRecord.getMinBufferSize(
            sampleRate, channelConfig, audioFormat
        )

        if (minBufferBytes == AudioRecord.ERROR || minBufferBytes == AudioRecord.ERROR_BAD_VALUE) {
            Log.e(TAG, "❌ AudioRecord.getMinBufferSize() failed: $minBufferBytes")
            return null
        }

        // Use a buffer large enough to hold multiple step-size windows.
        // Each short = 2 bytes. We want at least 4 full step windows in the buffer
        // to avoid overruns while the Goertzel computation runs.
        val stepBytes = ResonanceConfig.STEP_SIZE * 2   // 2 bytes per PCM_16BIT sample
        val desiredBufferBytes = maxOf(minBufferBytes, stepBytes * 4)

        Log.i(TAG, """
            |📊 AudioRecord config:
            |   Sample rate   : $sampleRate Hz
            |   Min buffer    : $minBufferBytes bytes
            |   Actual buffer : $desiredBufferBytes bytes
            |   Step size     : ${ResonanceConfig.STEP_SIZE} samples (${ResonanceConfig.STEP_SIZE * 1000.0 / sampleRate} ms)
            |   Goertzel N    : ${ResonanceConfig.GOERTZEL_N} samples
        """.trimMargin())

        return try {
            @Suppress("MissingPermission")  // Permission is checked before starting service
            AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate,
                channelConfig,
                audioFormat,
                desiredBufferBytes
            ).also { recorder ->
                if (recorder.state != AudioRecord.STATE_INITIALIZED) {
                    Log.e(TAG, "❌ AudioRecord failed to initialise (state=${recorder.state})")
                    recorder.release()
                    return null
                }
            }
        } catch (e: SecurityException) {
            Log.e(TAG, "❌ RECORD_AUDIO permission not granted", e)
            null
        }
    }

    // ═════════════════════════════════════════════════════════════════
    //  MAIN AUDIO CAPTURE LOOP
    // ═════════════════════════════════════════════════════════════════

    private fun startListening() {
        if (isListening) {
            Log.w(TAG, "⚠ Already listening — ignoring duplicate start")
            return
        }

        val recorder = initAudioRecord()
        if (recorder == null) {
            Log.e(TAG, "❌ Cannot start listening — AudioRecord init failed")
            stopSelf()
            return
        }

        audioRecord = recorder
        isListening = true

        // Launch the capture loop on a background coroutine
        serviceScope.launch {
            runCaptureLoop(recorder)
        }
    }

    private fun stopListening() {
        isListening = false

        audioRecord?.let { recorder ->
            try {
                if (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    recorder.stop()
                }
                recorder.release()
            } catch (e: Exception) {
                Log.e(TAG, "Error stopping AudioRecord", e)
            }
        }
        audioRecord = null

        fskDecoder.reset()
        Log.i(TAG, "⏹ Audio capture stopped")
    }

    /**
     * The hot loop: continuously reads [STEP_SIZE] samples from the mic,
     * runs Goertzel-based bit detection, and feeds results to the decoder.
     *
     * Runs on [Dispatchers.Default] to avoid blocking the main thread.
     */
    private suspend fun runCaptureLoop(recorder: AudioRecord) {
        val stepSize = ResonanceConfig.STEP_SIZE          // 2646 samples
        val goertzelN = ResonanceConfig.GOERTZEL_N        // 2205 samples
        val readBuffer = ShortArray(stepSize)

        Log.i(TAG, """
            |╔══════════════════════════════════════════════════════════╗
            |║     ULTRASONIC LISTENER — ACTIVE                        ║
            |║     Listening for ${ResonanceConfig.FREQ_0.toInt()} Hz / ${ResonanceConfig.FREQ_1.toInt()} Hz FSK            ║
            |╚══════════════════════════════════════════════════════════╝
        """.trimMargin())

        recorder.startRecording()
        var windowCount = 0L

        try {
            while (isListening && isActive) {
                // ── Read exactly STEP_SIZE samples ──────────────────
                val samplesRead = readFully(recorder, readBuffer, stepSize)

                if (samplesRead < stepSize) {
                    // Short read — likely shutting down
                    if (isListening) {
                        Log.w(TAG, "⚠ Short read: $samplesRead / $stepSize samples")
                    }
                    continue
                }

                // ── Run Goertzel on the first GOERTZEL_N samples ───
                // (the remaining GUARD_SAMPLES are the inter-symbol silence)
                val bitDecision = GoertzelDetector.decideBit(
                    samples = readBuffer,
                    offset = 0,
                    length = goertzelN
                )

                // ── Feed to streaming decoder ──────────────────────
                fskDecoder.feedBit(bitDecision)

                windowCount++

                // Periodic health log (every ~5 seconds = 5000ms / 60ms per step ≈ 83 windows)
                if (windowCount % 83 == 0L) {
                    Log.v(TAG, "♻ Window #$windowCount — decoder state: ${fskDecoder.state}")
                }
            }
        } catch (e: CancellationException) {
            Log.i(TAG, "Capture loop cancelled")
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error in capture loop", e)
        } finally {
            Log.i(TAG, "⏹ Capture loop exited after $windowCount windows")
        }
    }

    /**
     * Read exactly [count] samples from [recorder], blocking until the
     * buffer is full. This prevents partial-window Goertzel analysis.
     *
     * @return  Total samples actually read
     */
    private fun readFully(
        recorder: AudioRecord,
        buffer: ShortArray,
        count: Int
    ): Int {
        var totalRead = 0
        while (totalRead < count) {
            val remaining = count - totalRead
            val read = recorder.read(
                buffer, totalRead, remaining,
                AudioRecord.READ_BLOCKING
            )
            if (read < 0) {
                Log.e(TAG, "AudioRecord.read() error: $read")
                return totalRead
            }
            totalRead += read
        }
        return totalRead
    }

    // ═════════════════════════════════════════════════════════════════
    //  BROADCAST DECODED MESSAGES
    // ═════════════════════════════════════════════════════════════════

    private fun broadcastMessage(text: String) {
        Log.i(TAG, "📡 Broadcasting decoded message: \"$text\"")

        // Update notification with the decoded message
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification("Received: \"$text\""))

        // Send broadcast so Activities/Fragments can react
        val intent = Intent(ACTION_MESSAGE_DECODED).apply {
            putExtra(EXTRA_DECODED_TEXT, text)
            setPackage(packageName)   // restrict to our app
        }
        sendBroadcast(intent)
    }

    private fun broadcastState(state: FskDecoder.State) {
        val intent = Intent(ACTION_STATE_CHANGED).apply {
            putExtra(EXTRA_STATE, state.name)
            setPackage(packageName)
        }
        sendBroadcast(intent)
    }

    // ═════════════════════════════════════════════════════════════════
    //  NOTIFICATION  (required for foreground service)
    // ═════════════════════════════════════════════════════════════════

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW    // silent, persistent
            ).apply {
                description = "EchoNet ultrasonic mesh listener"
                setShowBadge(false)
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(contentText: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("EchoNet Triage")
            .setContentText(contentText)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    // ═════════════════════════════════════════════════════════════════
    //  WAKE LOCK  (keep CPU alive with screen off)
    // ═════════════════════════════════════════════════════════════════

    private fun acquireWakeLock() {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "EchoNet::UltrasonicListener"
        ).apply {
            acquire(60 * 60 * 1000L)   // 1 hour max — renew if needed
        }
        Log.d(TAG, "🔒 Wake lock acquired")
    }

    private fun releaseWakeLock() {
        wakeLock?.let {
            if (it.isHeld) it.release()
        }
        wakeLock = null
        Log.d(TAG, "🔓 Wake lock released")
    }
}
