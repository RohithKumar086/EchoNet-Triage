package com.echonet.triage.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Log

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║        RESONANCE-PROTOCOL  ·  ULTRASONIC BROADCASTER            ║
 * ║     Plays synthesized FSK audio through the device speaker      ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */
class UltrasonicBroadcaster {

    companion object {
        private const val TAG = "UltrasonicBroadcaster"
    }

    /**
     * Broadcasts the given PCM 16-bit short array using AudioTrack.
     * This method blocks until the entire buffer is written to the track.
     * Call this from a background thread to avoid blocking the main UI thread.
     */
    fun broadcast(pcm16: ShortArray) {
        val sampleRate = ResonanceConfig.SAMPLE_RATE
        val bufferSize = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )

        Log.i(TAG, "🔊 Preparing to broadcast ${pcm16.size} samples (${pcm16.size / sampleRate.toFloat()}s)")

        val audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(maxOf(bufferSize, pcm16.size * 2)) // *2 for 16-bit
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        try {
            audioTrack.play()
            
            // Write the samples to the audio track. This is a blocking call in STREAM mode.
            val written = audioTrack.write(pcm16, 0, pcm16.size)
            if (written != pcm16.size) {
                Log.w(TAG, "⚠ Wrote $written samples, expected ${pcm16.size}")
            } else {
                Log.i(TAG, "✅ Broadcast complete")
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ Error during broadcast: ${e.message}", e)
        } finally {
            // Give it a moment to finish playing the last few samples before releasing
            try {
                Thread.sleep(100)
            } catch (e: InterruptedException) {
                // Ignore
            }
            audioTrack.stop()
            audioTrack.release()
        }
    }
}
