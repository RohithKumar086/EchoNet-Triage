package com.echonet.triage.audio

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║           RESONANCE-PROTOCOL  ·  FSK ENCODER                    ║
 * ║     Converts text strings into near-ultrasonic audio arrays     ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * Direct Kotlin port of `fsk_encoder.py`.
 */
object FskEncoder {

    /**
     * Converts an ASCII string into a flat list of bits (MSB first).
     * Each character becomes 8 bits.
     */
    fun textToBits(text: String): List<Int> {
        val bits = mutableListOf<Int>()
        for (char in text) {
            val byteVal = char.code and 0xFF
            for (shift in 7 downTo 0) {
                bits.add((byteVal shr shift) and 1)
            }
        }
        return bits
    }

    /**
     * Generate a pure sine tone at [freq] Hz for [duration] seconds.
     * Applies a raised-cosine (Tukey) taper at both edges to suppress
     * spectral splatter from abrupt on/off transitions.
     *
     * Returns an array of Floats in the range [-1.0, 1.0].
     */
    fun generateTone(
        freq: Double,
        duration: Double,
        sampleRate: Int = ResonanceConfig.SAMPLE_RATE,
        amplitude: Double = ResonanceConfig.AMPLITUDE
    ): FloatArray {
        val nSamples = (sampleRate * duration).toInt()
        val signal = FloatArray(nSamples)

        for (i in 0 until nSamples) {
            val t = i.toDouble() / sampleRate
            signal[i] = (amplitude * sin(2.0 * PI * freq * t)).toFloat()
        }

        // Raised-cosine fade-in / fade-out
        val fadeLen = minOf(ResonanceConfig.FADE_SAMPLES, nSamples / 2)
        if (fadeLen > 0) {
            for (i in 0 until fadeLen) {
                val taper = (0.5 * (1.0 - cos(PI * i / fadeLen))).toFloat()
                signal[i] *= taper
                signal[nSamples - 1 - i] *= taper
            }
        }

        return signal
    }

    /**
     * Build the complete transmit waveform:
     * [silence] [preamble tones] [data tones] [silence]
     *
     * Returns a 16-bit PCM ShortArray ready for playback via AudioTrack.
     */
    fun encodeFsk(text: String): ShortArray {
        val payloadBits = textToBits(text)
        val allBits = ResonanceConfig.PREAMBLE_BITS.toList() + payloadBits

        val guardSamples = ResonanceConfig.GUARD_SAMPLES
        val guard = FloatArray(guardSamples) { 0f }

        // We use a list of FloatArrays to accumulate segments
        val segments = mutableListOf<FloatArray>()
        
        // Leading pad
        segments.add(FloatArray(ResonanceConfig.SAMPLES_PER_BIT) { 0f })

        for (bit in allBits) {
            val freq = if (bit == 1) ResonanceConfig.FREQ_1 else ResonanceConfig.FREQ_0
            val tone = generateTone(freq, ResonanceConfig.BIT_DURATION)
            segments.add(tone)
            segments.add(guard) // inter-symbol silence
        }

        // Trailing pad
        segments.add(FloatArray(ResonanceConfig.SAMPLES_PER_BIT) { 0f })

        // Concatenate all segments and convert to ShortArray
        var totalLength = 0
        for (seg in segments) {
            totalLength += seg.size
        }

        val pcm16 = ShortArray(totalLength)
        var offset = 0
        for (seg in segments) {
            for (sample in seg) {
                // Scale [-1.0, 1.0] to [-32768, 32767]
                var scaled = (sample * 32767).toInt()
                if (scaled > 32767) scaled = 32767
                if (scaled < -32768) scaled = -32768
                pcm16[offset++] = scaled.toShort()
            }
        }

        return pcm16
    }
}
