import 'dart:async';

import 'package:capricho_store/app/router.dart';
import 'package:capricho_store/core/notifications/fcm_service.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class CaprichoStoreApp extends ConsumerStatefulWidget {
  const CaprichoStoreApp({super.key});

  @override
  ConsumerState<CaprichoStoreApp> createState() => _CaprichoStoreAppState();
}

class _CaprichoStoreAppState extends ConsumerState<CaprichoStoreApp> {
  StreamSubscription<String>? _notificationTapSub;
  StreamSubscription<RemoteMessage>? _foregroundMessageSub;
  final GlobalKey<ScaffoldMessengerState> _scaffoldMessengerKey =
      GlobalKey<ScaffoldMessengerState>();

  @override
  void initState() {
    super.initState();

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
    _foregroundMessageSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp.router(
        title: 'Zentry',
        debugShowCheckedModeBanner: false,
        scaffoldMessengerKey: _scaffoldMessengerKey,
        theme: AppTheme.light,
        routerConfig: ref.watch(appRouterProvider),
      );
}
