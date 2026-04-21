package com.echonet.triage.audio

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║           RESONANCE-PROTOCOL  ·  ANDROID CONFIG                 ║
 * ║     Near-Ultrasonic FSK Codec — Shared Constants (Kotlin)       ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * Direct port of `dsp_sandbox/config.py`.
 * Every value here MUST stay in sync with the Python sandbox so that
 * Android nodes and desktop test rigs are interoperable.
 */
object ResonanceConfig {

    // ── Audio Hardware ──────────────────────────────────────────────
    const val SAMPLE_RATE: Int = 44_100         // Hz — Nyquist @ 22.05 kHz
    const val CHANNELS: Int = 1                 // mono
    const val BITS_PER_SAMPLE: Int = 16         // PCM_16BIT (most compatible)

    // ── FSK Carrier Frequencies ─────────────────────────────────────
    const val FREQ_0: Double = 18_000.0         // Hz — represents binary 0
    const val FREQ_1: Double = 19_000.0         // Hz — represents binary 1

    // ── Timing ──────────────────────────────────────────────────────
    const val BIT_DURATION: Double = 0.05       // seconds per bit (50 ms → 20 bps)
    const val GUARD_SILENCE: Double = 0.01      // seconds of silence between symbols

    // ── Amplitude ───────────────────────────────────────────────────
    const val AMPLITUDE: Double = 0.85          // peak amplitude [0..1]
    const val FADE_SAMPLES: Int = 32            // cosine-taper at segment edges

    // ── Preamble / Sync ─────────────────────────────────────────────
    //   Alternating 1-0 pattern the decoder locks onto before
    //   extracting payload bits.  8 bits = 400 ms total.
    val PREAMBLE_BITS: IntArray = intArrayOf(1, 0, 1, 0, 1, 0, 1, 0)

    // ── Thresholds ──────────────────────────────────────────────────
    const val ENERGY_THRESHOLD: Double = 0.005  // min Goertzel magnitude for "tone present"
    const val PREAMBLE_TOLERANCE: Int = 1       // max bit errors in preamble match

    // ── Derived Constants ───────────────────────────────────────────
    /** Number of PCM samples in one bit window (2205 @ 44.1 kHz) */
    val SAMPLES_PER_BIT: Int = (SAMPLE_RATE * BIT_DURATION).toInt()

    /** Number of silent samples between symbols (441 @ 44.1 kHz) */
    val GUARD_SAMPLES: Int = (SAMPLE_RATE * GUARD_SILENCE).toInt()

    /** Total step size per symbol: tone + guard (2646 samples) */
    val STEP_SIZE: Int = SAMPLES_PER_BIT + GUARD_SAMPLES

    /** Goertzel window length = one bit window */
    val GOERTZEL_N: Int = SAMPLES_PER_BIT

    // ── End-of-Transmission Detection ───────────────────────────────
    /** Consecutive silence windows before we consider the message over */
    const val SILENCE_STREAK_LIMIT: Int = 5
}
