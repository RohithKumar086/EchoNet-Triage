plugins {
    id("com.android.application") version "8.2.2"
    id("org.jetbrains.kotlin.android") version "1.9.22"
}

android {
    namespace = "com.echonet.triage"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.echonet.triage"
        minSdk = 26          // Android 8.0 — foreground service + notification channels
        targetSdk = 34
        versionCode = 1
        versionName = "0.3.0-phase3"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // ── AndroidX Core ───────────────────────────────────────────
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")

    // ── Kotlin Coroutines (background audio loop) ───────────────
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // ── Lifecycle (service-aware coroutine scopes) ──────────────
    implementation("androidx.lifecycle:lifecycle-service:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")

    // ──────────────────────────────────────────────────────────────
    //  NOTE: We do NOT need JTransforms or any FFT library.
    //
    //  The Goertzel algorithm computes the magnitude at a single
    //  DFT bin in O(N) with only real arithmetic — perfect when
    //  you just need two frequency bins (18 kHz and 19 kHz).
    //
    //  If you later need a full spectrogram (e.g., for debug UI),
    //  uncomment below:
    //
    //  implementation("com.github.wendykierp:JTransforms:3.1")
    // ──────────────────────────────────────────────────────────────
}
