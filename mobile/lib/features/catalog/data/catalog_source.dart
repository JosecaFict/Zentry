import 'dart:async';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Llamar dentro de `build` de una pantalla del catálogo: cuando vuelve la
/// conexión y la app estaba mostrando datos guardados, ejecuta [reload].
void refreshCatalogOnReconnect(WidgetRef ref, void Function() reload) {
  ref.listen<bool>(
    connectivityControllerProvider.select((state) => state.online),
    (previous, online) {
      if (previous != false || !online) return;
      if (!ref.read(catalogSourceProvider).usingCache) return;
      final source = ref.read(catalogSourceProvider.notifier);
      reload();
      // Se limpia después de que todas las pantallas abiertas recibieron el
      // aviso (los listeners se ejecutan en la misma vuelta).
      scheduleMicrotask(source.clear);
    },
  );
}

/// Indica si alguna pantalla del catálogo está mostrando datos guardados
/// (sin conexión) y de cuándo son los más antiguos.
class CatalogSourceState {
  const CatalogSourceState({this.oldestCachedAt});

  /// Fecha de la respuesta guardada más antigua que se mostró. null si todo
  /// lo que se ve vino de la red.
  final DateTime? oldestCachedAt;

  bool get usingCache => oldestCachedAt != null;
}

final catalogSourceProvider =
    NotifierProvider<CatalogSourceController, CatalogSourceState>(
      CatalogSourceController.new,
    );

class CatalogSourceController extends Notifier<CatalogSourceState> {
  @override
  CatalogSourceState build() => const CatalogSourceState();

  /// El repositorio devolvió una respuesta guardada en [updatedAt].
  void reportCacheHit(DateTime updatedAt) {
    final current = state.oldestCachedAt;
    if (current != null && !updatedAt.isBefore(current)) return;
    state = CatalogSourceState(oldestCachedAt: updatedAt);
  }

  /// Las pantallas recargaron con conexión: ya no se muestran datos viejos.
  void clear() {
    if (state.usingCache) state = const CatalogSourceState();
  }
}
