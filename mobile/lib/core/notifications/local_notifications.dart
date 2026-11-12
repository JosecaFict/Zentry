import 'dart:async';
import 'dart:developer' as developer;

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Notificaciones generadas por el propio teléfono (sin servidor ni Firebase).
/// Se usan para avisar al vendedor que una operación offline fue rechazada.
abstract class LocalNotifier {
  /// Rutas que el usuario abrió tocando una notificación.
  Stream<String> get onTap;

  /// Prepara el plugin (y detecta si la app se abrió desde una notificación).
  Future<bool> ensureInitialized();

  Future<void> show({
    required int id,
    required String title,
    required String body,
    String? route,
  });
}

final localNotifierProvider = Provider<LocalNotifier>((ref) {
  final notifier = PluginLocalNotifier();
  ref.onDispose(notifier.dispose);
  return notifier;
});

class PluginLocalNotifier implements LocalNotifier {
  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  final StreamController<String> _taps = StreamController.broadcast();
  Future<bool>? _ready;
  bool _permissionRequested = false;

  static const _channel = AndroidNotificationDetails(
    'offline_sync',
    'Ventas offline',
    channelDescription:
        'Avisos cuando una venta o reserva offline no se pudo registrar.',
    importance: Importance.high,
    priority: Priority.high,
  );

  @override
  Stream<String> get onTap => _taps.stream;

  Future<bool> _init() async {
    if (kIsWeb) return false;
    try {
      await _plugin.initialize(
        settings: const InitializationSettings(
          android: AndroidInitializationSettings('@mipmap/ic_launcher'),
          iOS: DarwinInitializationSettings(),
        ),
        onDidReceiveNotificationResponse: (response) {
          final route = response.payload;
          if (route != null && route.isNotEmpty) _taps.add(route);
        },
      );
      // Si la app se abrió tocando una notificación local.
      final launch = await _plugin.getNotificationAppLaunchDetails();
      final route = launch?.notificationResponse?.payload;
      if ((launch?.didNotificationLaunchApp ?? false) &&
          route != null &&
          route.isNotEmpty) {
        scheduleMicrotask(() => _taps.add(route));
      }
      return true;
    } catch (error) {
      developer.log(
        'No se pudieron iniciar las notificaciones locales: $error',
        name: 'LocalNotifications',
      );
      return false;
    }
  }

  /// Inicializa el plugin. Es seguro llamarlo varias veces.
  @override
  Future<bool> ensureInitialized() => _ready ??= _init();

  Future<void> _requestPermission() async {
    if (_permissionRequested) return;
    _permissionRequested = true;
    try {
      // Android 13+ (si FCM ya lo pidió, no vuelve a preguntar).
      await _plugin
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >()
          ?.requestNotificationsPermission();
      await _plugin
          .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin
          >()
          ?.requestPermissions(alert: true, badge: true, sound: true);
    } catch (_) {}
  }

  @override
  Future<void> show({
    required int id,
    required String title,
    required String body,
    String? route,
  }) async {
    if (!await ensureInitialized()) return;
    await _requestPermission();
    try {
      await _plugin.show(
        id: id,
        title: title,
        body: body,
        notificationDetails: const NotificationDetails(
          android: _channel,
          iOS: DarwinNotificationDetails(),
        ),
        payload: route,
      );
    } catch (error) {
      developer.log(
        'No se pudo mostrar la notificación: $error',
        name: 'LocalNotifications',
      );
    }
  }

  void dispose() => _taps.close();
}
