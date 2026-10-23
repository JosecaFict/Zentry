import 'package:capricho_store/app/app.dart';
import 'package:capricho_store/core/notifications/fcm_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await FcmService().initialize();
  runApp(const ProviderScope(child: ZentryApp()));
}
