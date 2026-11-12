import 'dart:async';

import 'package:capricho_store/core/network/api_client.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Cada cuánto se vuelve a verificar la conexión mientras la app está abierta.
const connectivityCheckInterval = Duration(seconds: 30);

/// Fuente de señales de red. Se separa para poder simularla en tests.
abstract class NetworkProbe {
  /// Avisa cuando cambia la interfaz de red (wifi, datos, ninguna).
  Stream<bool> get interfaceChanges;

  /// true si el teléfono tiene alguna interfaz de red activa.
  Future<bool> hasInterface();

  /// true si el backend responde: confirma que hay internet de verdad.
  Future<bool> reachesBackend();

  /// true con WiFi o cable: redes donde descargar imágenes no gasta datos.
  Future<bool> onUnmeteredNetwork();
}

class DefaultNetworkProbe implements NetworkProbe {
  DefaultNetworkProbe(this._dio);

  final Dio _dio;
  final Connectivity _connectivity = Connectivity();

  static bool _anyInterface(List<ConnectivityResult> results) =>
      results.any((result) => result != ConnectivityResult.none);

  @override
  Stream<bool> get interfaceChanges =>
      _connectivity.onConnectivityChanged.map(_anyInterface);

  @override
  Future<bool> hasInterface() async =>
      _anyInterface(await _connectivity.checkConnectivity());

  @override
  Future<bool> onUnmeteredNetwork() async {
    final results = await _connectivity.checkConnectivity();
    return results.contains(ConnectivityResult.wifi) ||
        results.contains(ConnectivityResult.ethernet);
  }

  @override
  Future<bool> reachesBackend() async {
    try {
      final response = await _dio.get<Object?>(
        '/health',
        options: Options(
          sendTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
        ),
      );
      final status = response.statusCode ?? 0;
      return status >= 200 && status < 500;
    } on DioException catch (error) {
      // Una respuesta 4xx también prueba que hay red hasta el servidor.
      final status = error.response?.statusCode;
      return status != null && status < 500;
    }
  }
}

final networkProbeProvider = Provider<NetworkProbe>(
  (ref) => DefaultNetworkProbe(ref.watch(dioProvider)),
);

class ConnectivityState {
  const ConnectivityState({
    this.online = true,
    this.checked = false,
    this.checkedAt,
    this.offlineSince,
  });

  /// Hay red y el backend responde.
  final bool online;

  /// Ya se hizo al menos una verificación (antes de eso se asume en línea).
  final bool checked;

  /// Momento de la última verificación; cambia en cada chequeo.
  final DateTime? checkedAt;

  /// Desde cuándo está sin conexión (null si está en línea).
  final DateTime? offlineSince;
}

/// Estado de conexión global de la app.
///
/// Combina tres señales:
/// - el stream de `connectivity_plus` (reacción inmediata al cambiar de red),
/// - un ping a `/health` (confirma que hay internet, no solo wifi),
/// - un chequeo cada [connectivityCheckInterval] como respaldo.
final connectivityControllerProvider =
    NotifierProvider<ConnectivityController, ConnectivityState>(
      ConnectivityController.new,
    );

class ConnectivityController extends Notifier<ConnectivityState> {
  StreamSubscription<bool>? _interfaceSubscription;
  Timer? _timer;
  Future<void>? _running;
  bool _foreground = true;

  @override
  ConnectivityState build() {
    final probe = ref.watch(networkProbeProvider);
    _interfaceSubscription = probe.interfaceChanges.listen((_) => check());
    final lifecycle = AppLifecycleListener(
      onHide: () {
        _foreground = false;
        _timer?.cancel();
      },
      onResume: () {
        _foreground = true;
        _startTimer();
        unawaited(check());
      },
    );
    ref.onDispose(() {
      lifecycle.dispose();
      _timer?.cancel();
      _interfaceSubscription?.cancel();
    });
    _startTimer();
    Future.microtask(check);
    return const ConnectivityState();
  }

  void _startTimer() {
    _timer?.cancel();
    if (!_foreground) return;
    _timer = Timer.periodic(connectivityCheckInterval, (_) => check());
  }

  /// Verifica la conexión ahora. Las llamadas simultáneas se agrupan.
  Future<void> check() => _running ??= _check().whenComplete(() {
    _running = null;
  });

  Future<void> _check() async {
    final probe = ref.read(networkProbeProvider);
    bool online;
    try {
      online = await probe.hasInterface() && await probe.reachesBackend();
    } catch (_) {
      online = false;
    }
    if (!ref.mounted) return;
    final now = DateTime.now();
    state = ConnectivityState(
      online: online,
      checked: true,
      checkedAt: now,
      offlineSince: online ? null : (state.offlineSince ?? now),
    );
  }

  /// Un repositorio detectó un error de red: verificar sin esperar al timer.
  void reportNetworkFailure() {
    if (state.online) unawaited(check());
  }
}
