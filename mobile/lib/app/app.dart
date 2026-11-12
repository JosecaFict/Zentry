import 'dart:async';

import 'package:capricho_store/app/router.dart';
import 'package:capricho_store/core/notifications/fcm_service.dart';
import 'package:capricho_store/core/notifications/local_notifications.dart';
import 'package:capricho_store/features/catalog/data/catalog_images.dart';
import 'package:capricho_store/features/catalog/data/catalog_snapshot_sync.dart';
import 'package:capricho_store/features/offline/presentation/offline_sync_controller.dart';
import 'package:capricho_store/features/offline/presentation/sync_conflicts_controller.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class ZentryApp extends ConsumerStatefulWidget {
  const ZentryApp({super.key});

  @override
  ConsumerState<ZentryApp> createState() => _ZentryAppState();
}

class _ZentryAppState extends ConsumerState<ZentryApp> {
  StreamSubscription<String>? _notificationTapSub;
  StreamSubscription<String>? _localNotificationTapSub;
  StreamSubscription<RemoteMessage>? _foregroundMessageSub;
  ProviderSubscription<OfflineSyncState>? _offlineSyncSub;
  ProviderSubscription<CatalogSnapshotState>? _catalogSnapshotSub;
  ProviderSubscription<CatalogImagesState>? _catalogImagesSub;
  final GlobalKey<ScaffoldMessengerState> _scaffoldMessengerKey =
      GlobalKey<ScaffoldMessengerState>();

  @override
  void initState() {
    super.initState();

    // Servicios globales: verificación de conexión cada 30 s y
    // sincronización automática de ventas offline mientras la app vive.
    _offlineSyncSub = ref.listenManual(
      offlineSyncControllerProvider,
      (_, _) {},
    );
    // Copia completa del catálogo para navegarlo y filtrarlo sin conexión.
    _catalogSnapshotSub = ref.listenManual(
      catalogSnapshotControllerProvider,
      (_, _) {},
    );
    // Imagen principal de cada producto guardada para verla sin conexión.
    _catalogImagesSub = ref.listenManual(
      catalogImagesControllerProvider,
      (_, _) {},
    );

    // Tocar una notificación local (venta offline rechazada).
    final localNotifier = ref.read(localNotifierProvider);
    _localNotificationTapSub = localNotifier.onTap.listen(
      (route) => ref.read(appRouterProvider).go(route),
    );
    unawaited(localNotifier.ensureInitialized());

    // Escuchar toques en notificaciones push (Lockscreen o Background)
    _notificationTapSub = FcmService().onNotificationTap.listen((route) {
      if (route.isNotEmpty) {
        ref.read(appRouterProvider).push(route);
      }
    });

    // Escuchar notificaciones en primer plano (Foreground)
    _foregroundMessageSub = FcmService().onForegroundMessage.listen((message) {
      HapticFeedback.mediumImpact();
      ref.read(notificationsProvider.notifier).refresh();
      ref.read(ordersProvider.notifier).refresh();
      if (message.data['type'] == 'SYNC_CONFLICTO') {
        // Supervisor: hay un conflicto nuevo. Vendedor: le resolvieron uno.
        unawaited(ref.read(syncConflictsProvider.notifier).refresh());
        unawaited(
          ref
              .read(offlineSyncControllerProvider.notifier)
              .refreshServerStatus(),
        );
      }

      final route = FcmService.extractRoute(message);
      final title = message.notification?.title ?? 'Notificación';
      final body = message.notification?.body ?? '';

      _scaffoldMessengerKey.currentState?.showSnackBar(
        SnackBar(
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          backgroundColor: AppColors.ink,
          duration: const Duration(seconds: 4),
          content: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: AppColors.cobalt.withValues(alpha: 0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.notifications_active_rounded,
                  color: AppColors.cobalt,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                        color: Colors.white,
                      ),
                    ),
                    if (body.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        body,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Color(0xFFE2E8F0),
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          action: route != null
              ? SnackBarAction(
                  label: 'Ver',
                  textColor: const Color(0xFF60A5FA),
                  onPressed: () {
                    ref.read(appRouterProvider).push(route);
                  },
                )
              : null,
        ),
      );
    });
  }

  @override
  void dispose() {
    _notificationTapSub?.cancel();
    _localNotificationTapSub?.cancel();
    _foregroundMessageSub?.cancel();
    _offlineSyncSub?.close();
    _catalogSnapshotSub?.close();
    _catalogImagesSub?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tenant = ref.watch(tenantControllerProvider).selected;
    return MaterialApp.router(
        title: 'Zentry',
        debugShowCheckedModeBanner: false,
        scaffoldMessengerKey: _scaffoldMessengerKey,
        theme: AppTheme.forTenant(tenant?.color),
        routerConfig: ref.watch(appRouterProvider),
      );
  }
}
