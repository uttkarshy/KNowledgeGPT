# Android development and release

The app lives in mobile/ and shares the existing KnowledgeGPT service. Expo SDK 55, React Native 0.83, TypeScript and Expo Router use the checked-in npm lockfile. Version 1.0.0 (1) uses com.utkarshlabs.knowledgegpt, compile/target API 36. app.json contains the adaptive icon, splash, permission exclusions and production HTTPS policy.

## Local development

Use Node 22.13+ (or Node 24), npm, JDK 17, and Android SDK Platform 36, Build Tools 36.0.0, NDK 27.1.12297006, CMake 3.22.1 and platform-tools. Set JAVA_HOME and ANDROID_HOME, then run from mobile/.

```sh
npm ci
npm run typecheck
npm test
npx expo prebuild --platform android --no-install
npx expo run:android
```

During development the debug variant uses Metro. The app defaults to https://knowledgegpt.utkarshlabs.com. To test an authorized staging deployment, set EXPO_PUBLIC_API_ORIGIN to its HTTPS origin before compiling. Only this public origin belongs in the client. Provider, upload storage and database credentials belong on the service. Use npm ci on a clean checkout when reproducing a build.

## Standalone phone preview

From mobile/android run the following on Linux or macOS. On Windows, use gradlew.bat. CI creates a temporary debug certificate and builds ARM64 (phones) and x86_64 (emulators). A locally generated release variant uses the native template’s test signing configuration. It is suitable for a preview only.

```sh
./gradlew :app:assembleRelease :app:assembleDebug -PreactNativeArchitectures=arm64-v8a,x86_64 --max-workers=2
adb install -r app/build/outputs/apk/release/app-release.apk
adb shell am start -n com.utkarshlabs.knowledgegpt/.MainActivity
```

The standalone preview contains its JavaScript bundle. On a phone open the downloaded preview APK, grant the installing app Android’s install permission if requested, and open KnowledgeGPT. A signature mismatch means Android already has this package signed with another key. Check for local work before removing a prior test installation. Preview keys have a separate identity from the Play upload key.

## Play bundle

The owner authorized the existing EAS account. This checkout currently has no linked project ID, and the EAS identity check returned “Not logged in”. Obtain the existing KnowledgeGPT project UUID and authenticated access through a protected environment. Never put an Expo token or upload keystore in an issue or chat. The checked-in eas.json defines preview APK and production AAB profiles. Confirm the package, unused version code, EAS project identity, available build allowance and existing upload certificate fingerprint. The owner controls credential selection or creation. Use the production profile with EAS-managed upload credentials or the owner’s established private release-signing process.

```sh
cd mobile
npx --yes eas-cli@27.11.0 whoami
npx --yes eas-cli@27.11.0 init --id "$KNOWLEDGEGPT_EAS_PROJECT_ID" --non-interactive
npx --yes eas-cli@27.11.0 project:info
npx --yes eas-cli@27.11.0 build --platform android --profile production --local --non-interactive --freeze-credentials --output /tmp/KnowledgeGPT-release.aab
```

Use the verified existing project UUID for KNOWLEDGEGPT_EAS_PROJECT_ID and review the resulting public app-config link before committing. The local Linux/macOS build uses the existing EAS signing credential and local build tools. If credentials are missing, stop before provisioning. Use the EAS hosted build only after verifying available allowance or obtaining approval for a charge. Keep signing material out of Git and CI logs. EAS Submit is separate from building. For a returned bundle, verify with jarsigner, compare its certificate fingerprint to Play Console, use bundletool validate, generate device APKs, and verify package, target, version, permissions, 16 KB ZIP and ELF alignment on the bundle-derived APKs. Exercise the Play-delivered build in the owner’s approved test track before any production submission.

## Android development sequence

1. Source audit and public read-only connectivity checks.
2. Secure sessions, account lifecycle, workspace and document management.
3. SSE chat, history and source references.
4. Branch-only service support, erasure intake, upload and isolation fixes.
5. Disposable backend acceptance test, SDK checks, APK verification and emulator/device tests.
6. Operator deployment, release-key verification, review account and final Play declarations.
