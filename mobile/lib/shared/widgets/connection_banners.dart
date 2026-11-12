import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/catalog/data/catalog_source.dart';
import 'package:capricho_store/features/offline/presentation/offline_sync_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

/// Avisos globales que van encima de la barra de navegación inferior:
/// operaciones offline rechazadas y estado sin conexión.
class ConnectionBanners extends StatelessWidget {
  const ConnectionBanners({super.key});

  @override
  Widget build(BuildContext context) => const Column(
    mainAxisSize: MainAxisSize.min,
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [SyncAlertBanner(), OfflineBanner()],
  );
}

/// "Sin conexión · mostrando datos guardados hace 2 h".
class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connectivity = ref.watch(connectivityControllerProvider);
    if (!connectivity.checked || connectivity.online) {
      return const SizedBox.shrink();
    }
    final cachedAt = ref.watch(catalogSourceProvider).oldestCachedAt;
    final detail = cachedAt == null
        ? 'Algunas funciones necesitan internet.'
        : 'Mostrando datos guardados ${describeAge(cachedAt)}.';
    return Semantics(
      liveRegion: true,
      child: Material(
        color: const Color(0xFFFFF1E7),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
          child: Row(
            children: [
              const Icon(
                Icons.cloud_off_outlined,
                size: 18,
                color: AppColors.warning,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text.rich(
                  TextSpan(
                    children: [
                      const TextSpan(
                        text: 'Sin conexión · ',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      TextSpan(text: detail),
                    ],
                  ),
                  style: const TextStyle(fontSize: 13, color: AppColors.ink),
                ),
              ),
              TextButton(
                onPressed: () =>
                    ref.read(connectivityControllerProvider.notifier).check(),
                child: const Text('Reintentar'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// "⚠ 1 venta no se registró · Motivo: no había stock". Sigue visible hasta
/// que la operación se marque como revisada en la pantalla Offline.
class SyncAlertBanner extends ConsumerWidget {
  const SyncAlertBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final failures = ref.watch(
      offlineSyncControllerProvider.select((state) => state.failures),
    );
    if (failures.isEmpty) return const SizedBox.shrink();
    final first = failures.first;
    final title = failures.length == 1
        ? first.title
        : '${failures.length} operaciones offline no se registraron';
    final reason = failures.length == 1
        ? 'Motivo: ${first.operation.failureReason}'
        : 'Toca para ver el motivo de cada una.';
    return Semantics(
      liveRegion: true,
      button: true,
      child: Material(
        color: const Color(0xFFFFE7E3),
        child: InkWell(
          onTap: () => context.go(offlineAlertRoute),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 12, 10),
            child: Row(
              children: [
                const Icon(
                  Icons.error_outline_rounded,
                  size: 20,
                  color: AppColors.danger,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: AppColors.ink,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        reason,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.ink,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(
                  Icons.chevron_right_rounded,
                  color: AppColors.danger,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// "hace 5 min", "hace 2 h", "el 03/11".
String describeAge(DateTime moment, {DateTime? now}) {
  final diff = (now ?? DateTime.now()).difference(moment);
  if (diff.inMinutes < 1) return 'de hace un momento';
  if (diff.inMinutes < 60) return 'de hace ${diff.inMinutes} min';
  if (diff.inHours < 24) return 'de hace ${diff.inHours} h';
  if (diff.inDays < 7) {
    return 'de hace ${diff.inDays} ${diff.inDays == 1 ? 'día' : 'días'}';
  }
  final local = moment.toLocal();
  final day = local.day.toString().padLeft(2, '0');
  final month = local.month.toString().padLeft(2, '0');
  return 'del $day/$month';
}
