# VisionLeader UFV — App móvil

Cliente Flutter (Android / iOS) del sistema VisionLeader UFV. Permite a un usuario con discapacidad visual formular consultas por voz, capturar imágenes del entorno y recibir instrucciones de navegación paso a paso por TTS.

## Requisitos

- Flutter SDK
- Backend de planificación corriendo (ver `README.md` en la raíz del repo)

## Ejecución

```bash
flutter pub get
flutter run
```

## Configuración del backend

La URL base de la API se define en `lib/core/app_config.dart`. Se puede sobreescribir en tiempo de build sin tocar el código:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.50:8000
```

En el emulador Android usa `http://10.0.2.2:8000` para alcanzar el host.

### Atajo: auto-detectar la IP del host (Windows)

Para no tener que mirar la IP a mano cada vez que cambia la red, hay un script PowerShell que la detecta y lanza la app:

```powershell
cd mobile_app
.\run_dev.ps1
```

Por defecto usa el puerto 8000. Para otro puerto: `.\run_dev.ps1 -Port 8001`.

## Estructura

- `lib/screens/home_screen.dart` — pantalla inicial.
- `lib/screens/conversation/` — flujo conversacional (voz, foto, TTS, pasos).
- `lib/services/api_service.dart` — cliente HTTP del backend.
- `lib/core/app_config.dart` — configuración de URL y timeouts.
- `lib/core/app_theme.dart` — tema oscuro.
