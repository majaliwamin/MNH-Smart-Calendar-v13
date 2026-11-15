# MNH Calendar Flutter client

Generate the Android runner if it is not present, then build the native client:

```powershell
flutter create --platforms=android,web --project-name mnh_calendar .
flutter pub get
flutter analyze
flutter build apk --release --dart-define=API_BASE_URL=https://mnh-smart-calendar-v13.onrender.com
```

Install `build\app\outputs\flutter-apk\app-release.apk` on Android and allow notifications and exact alarms. The native client schedules five-minute reminders locally; the app and internet are not required when they fire. Keep notification sound enabled. Do Not Disturb, silent mode and battery restrictions can still suppress sound. The browser-installed PWA cannot provide these guarantees.
