abstract final class Environment {
  static const _definedUrl = String.fromEnvironment('API_BASE_URL');
  static const productionUrl =
      'https://zentry-production-319f.up.railway.app/api/v1';
  static const localUrl = 'http://10.0.2.2:8000/api/v1';

  /// Por defecto conecta a la API desplegada en Railway.
  /// Si se desea usar local, se puede pasar --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
  static String get apiBaseUrl {
    if (_definedUrl.isNotEmpty) return _definedUrl;
    return productionUrl;
  }
}
