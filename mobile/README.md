# MNH Calendar Flutter client

Open this `mobile` directory as the Flutter project in VS Code. The app uses the shared FastAPI service; it does not create a separate database.

```powershell
flutter pub get
flutter analyze
# Generate Android and web runner folders if they are not present yet.
flutter create --platforms=android,web --project-name mnh_calendar .
flutter pub get
flutter run --dart-define=API_BASE_URL=https://YOUR-RENDER-SERVICE.onrender.com
```

For Android emulator development against a local server, the default API address is `http://10.0.2.2:8000`. For a physical phone on the same LAN, set `API_BASE_URL` to the development PC LAN address. For access from other networks, use the deployed Render HTTPS URL.

The app opens on the Weekly Schedule. Dashboard, Weekly Schedule and Upcoming Academic Activities are permanent on-screen tabs, so they are not repeated in the hamburger drawer. The drawer contains the remaining programme sections, with Settings separated and anchored at the bottom. Public users can view shared data; editing requires the existing authorised passwords. Analytics are only available to HOD, Coordinator and Executive Dean accounts. When scheduling, date and time fields open the native pickers; past dates are greyed out and the latest date is three years from today.
