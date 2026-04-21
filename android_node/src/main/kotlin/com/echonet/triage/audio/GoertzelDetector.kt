package com.echonet.triage.audio

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sqrt

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║           RESONANCE-PROTOCOL  ·  GOERTZEL DETECTOR              ║
 * ║        Single-bin DFT for 18 kHz / 19 kHz tone detection        ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * The Goertzel algorithm computes the DFT magnitude at a single
 * frequency bin in O(N) using only real arithmetic.  This is far
 * more efficient than running a full FFT when you only need two
 * bins (FREQ_0 and FREQ_1).
 *
 * Goertzel recurrence:
 *     coeff = 2 · cos(2π · k / N)
 *     s[n]  = x[n] + coeff · s[n-1] − s[n-2]
 *
 * Final magnitude:
 *     power = s[N-1]² + s[N-2]² − coeff · s[N-1] · s[N-2]
 *     magnitude = √power
 *
 * Direct port of `goertzel_magnitude()` from `dsp_sandbox/fsk_decoder.py`.
 */
object GoertzelDetector {

    /**
     * Compute the Goertzel magnitude at [targetFreq] over PCM 16-bit samples.
     *
     * @param samples   Raw PCM 16-bit audio buffer
     * @param offset    Start index into [samples]
     * @param length    Number of samples to analyse (typically [ResonanceConfig.GOERTZEL_N])
     * @param targetFreq  The frequency bin to evaluate (Hz)
     * @param sampleRate  Samples per second (default 44100)
     * @return  Non-negative magnitude value
     */
    fun magnitude(
        samples: ShortArray,
        offset: Int,
        length: Int,
        targetFreq: Double,
        sampleRate: Int = ResonanceConfig.SAMPLE_RATE
    ): Double {
        // Normalised frequency index (may be fractional)
        val k = targetFreq * length / sampleRate
        val omega = 2.0 * PI * k / length
        val coeff = 2.0 * cos(omega)

        // Goertzel recurrence — purely sequential, no allocations
        var s1 = 0.0   // s[n-1]
        var s2 = 0.0   // s[n-2]

        for (i in 0 until length) {
            // Normalise 16-bit PCM to [-1.0, 1.0]
            val x = samples[offset + i].toDouble() / 32768.0
            val s = x + coeff * s1 - s2
            s2 = s1
            s1 = s
        }

        // Final power calculation
        val power = s1 * s1 + s2 * s2 - coeff * s1 * s2
        return sqrt(max(power, 0.0))
    }

    /**
     * Convenience: run Goertzel at both FSK frequencies and return a [BitDecision].
     *
     * @return  [BitDecision.ONE], [BitDecision.ZERO], or [BitDecision.SILENCE]
     */
    fun decideBit(
        samples: ShortArray,
        offset: Int,
        length: Int = ResonanceConfig.GOERTZEL_N
    ): BitDecision {
        val mag0 = magnitude(samples, offset, length, ResonanceConfig.FREQ_0)
        val mag1 = magnitude(samples, offset, length, ResonanceConfig.FREQ_1)

        // Normalise to per-sample magnitude (matches Python's norm_0 / norm_1)
        val norm0 = mag0 / length
        val norm1 = mag1 / length

        // Both below noise floor → silence
        if (norm0 < ResonanceConfig.ENERGY_THRESHOLD &&
            norm1 < ResonanceConfig.ENERGY_THRESHOLD
        ) {
            return BitDecision.SILENCE
        }

        return if (mag1 > mag0) BitDecision.ONE else BitDecision.ZERO
    }

    /**
     * Tri-state bit decision matching the Python decoder's `decide_bit()`.
     */
    enum class BitDecision(val value: Int?) {
        ZERO(0),
        ONE(1),
        SILENCE(null)
    }
}
