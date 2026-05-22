import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Read the Google Maps API key from android/local.properties (gitignored) so it is
// never committed. Set MAPS_API_KEY there for Maps to work on the device.
val localProperties = Properties()
val localPropertiesFile = rootProject.file("local.properties")
if (localPropertiesFile.exists()) {
    localPropertiesFile.inputStream().use { localProperties.load(it) }
}
val mapsApiKey = localProperties.getProperty("MAPS_API_KEY") ?: ""

android {
    namespace = "com.example.visionleader_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.example.visionleader_app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        // Injected into AndroidManifest.xml as the MAPS_API_KEY placeholder.
        manifestPlaceholders["MAPS_API_KEY"] = mapsApiKey
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    // Extract native libs on install so the bundled whisper-server binary
    // lives as an executable file in applicationInfo.nativeLibraryDir rather
    // than being mmap'd from inside the APK (which prevents exec on Android).
    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }
}

flutter {
    source = "../.."
}

configurations.all {
    resolutionStrategy {
        // Keep a single AndroidX Lifecycle line to avoid duplicate classes in dex merge.
        force("androidx.lifecycle:lifecycle-viewmodel-savedstate:2.8.7")
        force("androidx.lifecycle:lifecycle-viewmodel:2.8.7")
        force("androidx.lifecycle:lifecycle-livedata-core:2.8.7")
        force("androidx.lifecycle:lifecycle-runtime:2.8.7")
        force("androidx.savedstate:savedstate:1.2.1")
    }
}
