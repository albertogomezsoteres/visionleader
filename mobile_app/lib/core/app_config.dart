/// Backend base URL for HTTP calls.
///
/// Override at build time, e.g. physical device on LAN:
/// `flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000`
///
/// Android emulator: [defaultBaseUrl] maps the host machine's localhost.
class AppConfig {
  AppConfig._();

  static const String defaultBaseUrl = 'http://192.168.1.51:8000';

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: defaultBaseUrl,
  );

  static const Duration analyzeImageTimeout = Duration(seconds: 60);
  static const Duration planTimeout = Duration(seconds: 60);
  static const Duration conversationTimeout = Duration(seconds: 30);
  static const Duration gpsRouteTimeout = Duration(seconds: 15);
}
