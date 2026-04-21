package com.echonet.triage.audio

import android.util.Log

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║           RESONANCE-PROTOCOL  ·  STREAMING FSK DECODER          ║
 * ║     Real-time state machine: preamble → payload → ASCII text    ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * Port of `decode_buffer()` from `dsp_sandbox/fsk_decoder.py`, but
 * redesigned for **streaming** (Android processes audio in chunks,
 * not a single monolithic buffer).
 *
 * State machine:
 *     SCANNING          →  looking for preamble pattern
 *     PREAMBLE_LOCKED   →  preamble matched, transitioning to payload
 *     EXTRACTING        →  collecting payload bits
 *     COMPLETE          →  message fully received (silence streak exceeded)
 */
class FskDecoder(
    private val onMessageDecoded: (String) -> Unit,
    private val onStatusChanged: (State) -> Unit = {}
) {

    companion object {
        private const val TAG = "FskDecoder"
    }

    // ── Decoder state machine ───────────────────────────────────────
    enum class State {
        SCANNING,           // Idle — watching for preamble
        PREAMBLE_LOCKED,    // Preamble detected, entering payload extraction
        EXTRACTING,         // Collecting payload bits
        COMPLETE            // End-of-transmission detected
    }

    var state: State = State.SCANNING
        private set

    // Rolling window of recent bit decisions (for preamble matching)
    private val recentBits = mutableListOf<Int?>()

    // Payload bit accumulator
    private val payloadBits = mutableListOf<Int>()

    // Consecutive silence windows (end-of-transmission detection)
    private var silenceStreak: Int = 0

    // Stats
    private var totalWindowsProcessed: Long = 0
    private var preambleLockWindow: Long = -1

    /**
     * Feed a single bit decision from the Goertzel detector.
     * Call this once per STEP_SIZE audio window.
     */
    fun feedBit(decision: GoertzelDetector.BitDecision) {
        totalWindowsProcessed++

        when (state) {
            State.SCANNING -> handleScanning(decision)
            State.PREAMBLE_LOCKED -> handleExtracting(decision)
            State.EXTRACTING -> handleExtracting(decision)
            State.COMPLETE -> { /* ignore further input until reset */ }
        }
    }

    // ── SCANNING: look for preamble ────────────────────────────────

    private fun handleScanning(decision: GoertzelDetector.BitDecision) {
        recentBits.add(decision.value)

        // Keep only the last N bits (preamble length + margin)
        val preambleLen = ResonanceConfig.PREAMBLE_BITS.size
        if (recentBits.size > preambleLen * 2) {
            recentBits.removeAt(0)
        }

        // Check for preamble match
        if (matchPreamble()) {
            state = State.PREAMBLE_LOCKED
            preambleLockWindow = totalWindowsProcessed
            Log.i(TAG, "✅ Preamble locked at window $totalWindowsProcessed")
            onStatusChanged(state)

            // Immediately transition to extracting
            state = State.EXTRACTING
            onStatusChanged(state)
        }
    }

    // ── EXTRACTING: collect payload bits ────────────────────────────

    private fun handleExtracting(decision: GoertzelDetector.BitDecision) {
        when (decision) {
            GoertzelDetector.BitDecision.SILENCE -> {
                silenceStreak++
                if (silenceStreak >= ResonanceConfig.SILENCE_STREAK_LIMIT) {
                    // End of transmission detected
                    finaliseMessage()
                }
            }
            else -> {
                silenceStreak = 0
                payloadBits.add(decision.value!!)

                // Log progress every 8 bits (1 character)
                if (payloadBits.size % 8 == 0) {
                    val chars = payloadBits.size / 8
                    Log.d(TAG, "📦 Extracted ${payloadBits.size} bits → $chars chars so far")
                }
            }
        }
    }

    // ── PREAMBLE MATCHING ──────────────────────────────────────────

    /**
     * Hamming-distance preamble match.
     * Identical to `match_preamble()` in the Python decoder.
     */
    private fun matchPreamble(): Boolean {
        val preamble = ResonanceConfig.PREAMBLE_BITS
        val n = preamble.size

        if (recentBits.size < n) return false

        val window = recentBits.subList(recentBits.size - n, recentBits.size)
        var errors = 0
        for (i in 0 until n) {
            if (window[i] == null || window[i] != preamble[i]) {
                errors++
            }
        }

        return errors <= ResonanceConfig.PREAMBLE_TOLERANCE
    }

    // ── BITS → TEXT CONVERSION ─────────────────────────────────────

    /**
     * Convert accumulated payload bits to ASCII text (MSB first, 8 per char).
     * Direct port of `bits_to_text()` from `dsp_sandbox/fsk_decoder.py`.
     */
    private fun bitsToText(bits: List<Int>): String {
        val sb = StringBuilder()
        var i = 0
        while (i + 7 < bits.size) {
            var byteVal = 0
            for (j in 0 until 8) {
                byteVal = (byteVal shl 1) or bits[i + j]
            }
            sb.append((byteVal and 0x7F).toChar())
            i += 8
        }
        return sb.toString()
    }

    // ── FINALISE & RESET ───────────────────────────────────────────

    private fun finaliseMessage() {
        state = State.COMPLETE
        onStatusChanged(state)

        if (payloadBits.isEmpty()) {
            Log.w(TAG, "⚠ Preamble detected but no payload bits received.")
            reset()
            return
        }

        val text = bitsToText(payloadBits)
        val bitCount = payloadBits.size
        val charCount = bitCount / 8

        Log.i(TAG, "╔═══════════════════════════════════════════╗")
        Log.i(TAG, "║  DECODED: \"$text\"")
        Log.i(TAG, "║  $bitCount bits → $charCount characters")
        Log.i(TAG, "╚═══════════════════════════════════════════╝")

        // Deliver to callback
        onMessageDecoded(text)

        // Auto-reset for next message
        reset()
    }

    /**
     * Reset all state for the next incoming message.
     * Called automatically after message delivery, or manually
     * if the listener is restarted.
     */
    fun reset() {
        state = State.SCANNING
        recentBits.clear()
        payloadBits.clear()
        silenceStreak = 0
        totalWindowsProcessed = 0
        preambleLockWindow = -1
        onStatusChanged(state)
        Log.d(TAG, "🔄 Decoder reset — scanning for next preamble")
    }
}
