plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.beta.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.beta.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 6
        versionName = "0.6.0"

        // BETA-CLOUD (ver api/contrato.py e memory/beta_cloud_client.py
        // no núcleo desktop) — igual ao .env.example de lá: nunca
        // hardcoded, vazio por padrão. Sem valor aqui, o app funciona
        // 100% local/offline (ver rede/BetaCloudApi.kt).
        buildConfigField("String", "BETA_CLOUD_PROJECT_URL", "\"\"")
        buildConfigField("String", "BETA_CLOUD_PUBLISHABLE_KEY", "\"\"")
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.camera:camera-core:1.4.0")
    implementation("androidx.camera:camera-camera2:1.4.0")
    implementation("androidx.camera:camera-lifecycle:1.4.0")
    implementation("androidx.camera:camera-view:1.4.0")
}
