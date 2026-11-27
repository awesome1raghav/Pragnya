# NEXTRON Android

Kotlin / Compose client in `App/`. Gradle wrapper: `gradlew.bat :App:assembleDebug` (JDK 17 and Android SDK 35). Debug APK: `../../artifacts/NEXTRON.apk`.

Backend: start PostgreSQL and the existing FastAPI API plus worker from the repository root. Configure the app's Connect screen with `http://<computer-LAN-IP>:8000/api/v1/` on a trusted local network, or HTTPS for a remote server. `localhost` on a physical phone points to the phone. The backend currently has no multiuser authentication; do not expose it to the public internet.

Implemented client flows: backend readiness, case creation and selection, file picker, Android share intake, original upload, T-MIR job polling, current findings and artifacts, source records and URL submission, reports, local NEX-BTK comparison and bounded expansion controls, screen capture/recording, and a draggable overlay. Capture needs fresh Android MediaProjection consent for each session. The overlay can be dismissed in-app or from its notification.

Verified on a connected Android 16 phone: APK install and launch; backend readiness; case creation; image, video, and audio share uploads into an isolated test database; corresponding T-MIR jobs and findings; overlay service visible. The three jobs were `PARTIALLY_COMPLETED`, reflecting backend limitations. The foreground capture prompt appeared; capture completion and recording were not verified. The NEX-BTK UI additions and accessibility fix were made after the last successful APK build and require rebuild/reinstall.

Not implemented: optional crop selection, playback audio capture, offline analysis, deepfake models in the APK, or comprehensive external source discovery. Only backend-provided results are shown.
