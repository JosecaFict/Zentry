import 'dart:async';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/catalog/data/catalog_repository.dart';
import 'package:capricho_store/features/catalog/data/catalog_snapshot_sync.dart';
import 'package:capricho_store/features/offline/data/offline_database.dart';
import 'package:dio/dio.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// Caché de imágenes del catálogo: más grande y duradera que la de por
/// defecto (≈200 imágenes, 30 días), para que lo ya visto siga offline.
final catalogImageCacheManager = CacheManager(
  Config(
    'catalogImages',
    stalePeriod: const Duration(days: 365),
    maxNrOfCacheObjects: 5000,
  ),
);

/// Ancho de la copia que se guarda para ver sin conexión.
const offlineImageWidth = 800;

/// Tamaño máximo aceptado por imagen descargada.
const offlineImageMaxBytes = 8 * 1024 * 1024;

/// Descargas simultáneas de imágenes.
const offlineImageConcurrency = 4;

/// Versión liviana de una imagen de Cloudinary (800 px, calidad automática).
/// Otras URLs se descargan tal cual.
String offlineImageUrl(String url) {
  final uri = Uri.tryParse(url);
  if (uri == null ||
      !uri.host.endsWith('cloudinary.com') ||
      !uri.path.contains('/image/upload/')) {
    return url;
  }
  return url.replaceFirst(
    '/image/upload/',
    '/image/upload/c_limit,w_$offlineImageWidth,q_auto/',
  );
}

/// Nombre de archivo estable para una URL (hash FNV-1a de 64 bits).
String offlineImageFileName(String url) {
  var hash = 0xcbf29ce484222325;
  for (final unit in url.codeUnits) {
    hash ^= unit;
    hash *= 0x100000001b3; // Los int de Dart nativo ya envuelven en 64 bits.
  }
  final path = Uri.tryParse(url)?.path ?? '';
  final ext = p.extension(path).toLowerCase();
  final safeExt = const {'.jpg', '.jpeg', '.png', '.webp', '.gif'}.contains(ext)
      ? ext
      : '.img';
  return '${hash.toUnsigned(64).toRadixString(16).padLeft(16, '0')}$safeExt';
}

/// Carpeta raíz de imágenes offline (documentos de la app: el sistema no la
/// limpia como la carpeta de caché).
final catalogImageRootProvider = Provider<Future<Directory> Function()>(
  (ref) =>
      () async => Directory(
        p.join(
          (await getApplicationDocumentsDirectory()).path,
          'catalog_images',
        ),
      ),
);

/// Dio sin interceptores: las imágenes son públicas y no llevan token.
final catalogImageDioProvider = Provider<Dio>(
  (ref) => Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
      responseType: ResponseType.bytes,
    ),
  ),
);

class CatalogImagesState {
  const CatalogImagesState({
    this.paths = const {},
    this.downloading = false,
    this.missing = 0,
    this.error,
  });

  /// URL original → ruta absoluta del archivo guardado.
  final Map<String, String> paths;
  final bool downloading;

  /// Imágenes principales que todavía faltan descargar.
  final int missing;
  final String? error;

  CatalogImagesState copyWith({
    Map<String, String>? paths,
    bool? downloading,
    int? missing,
    String? error,
    bool clearError = false,
  }) => CatalogImagesState(
    paths: paths ?? this.paths,
    downloading: downloading ?? this.downloading,
    missing: missing ?? this.missing,
    error: clearError ? null : (error ?? this.error),
  );
}

/// Guarda la imagen principal de cada producto para verla sin conexión.
///
/// - Se ejecuta tras cada descarga del catálogo completo y en los chequeos de
///   conexión, **solo con WiFi**.
/// - Descarga únicamente lo que falta y borra las imágenes de productos que
///   ya no están en el catálogo.
final catalogImagesControllerProvider =
    NotifierProvider<CatalogImagesController, CatalogImagesState>(
      CatalogImagesController.new,
    );

class CatalogImagesController extends Notifier<CatalogImagesState> {
  Future<void>? _running;
  DateTime? _lastFailure;

  String? get _tenant => ref.read(tenantControllerProvider).selected?.slug;

  @override
  CatalogImagesState build() {
    ref.listen(
      tenantControllerProvider.select((state) => state.selected?.slug),
      (previous, next) {
        if (previous == next) return;
        _lastFailure = null;
        state = const CatalogImagesState();
        unawaited(_loadPaths());
      },
    );
    ref.listen(
      catalogSnapshotControllerProvider.select((state) => state.syncedAt),
      (previous, next) {
        if (next != null && next != previous) unawaited(maybeDownload());
      },
    );
    ref.listen(connectivityControllerProvider, (previous, next) {
      if (next.online && next.checkedAt != previous?.checkedAt) {
        unawaited(maybeDownload());
      }
    });
    Future.microtask(_loadPaths);
    return const CatalogImagesState();
  }

  Future<Directory> _tenantDir(String tenant) async => Directory(
    p.join((await ref.read(catalogImageRootProvider)()).path, tenant),
  );

  Future<void> _loadPaths() async {
    final tenant = _tenant;
    if (tenant == null) return;
    try {
      final stored = await ref
          .read(offlineDatabaseProvider)
          .catalogImages(tenant);
      final dir = await _tenantDir(tenant);
      if (!ref.mounted || _tenant != tenant) return;
      state = state.copyWith(
        paths: {
          for (final entry in stored.entries)
            entry.key: p.join(dir.path, entry.value),
        },
      );
    } catch (error) {
      developer.log('No se pudieron leer las imágenes: $error', name: 'Images');
    }
  }

  /// Descarga lo que falte si hay WiFi y no falló hace poco.
  Future<void> maybeDownload({DateTime? now}) {
    final last = _lastFailure;
    if (last != null &&
        (now ?? DateTime.now()).difference(last) < catalogSnapshotRetryDelay) {
      return _running ?? Future.value();
    }
    return _running ??= _download().whenComplete(() => _running = null);
  }

  Future<void> _download() async {
    final tenant = _tenant;
    if (tenant == null || !ref.read(connectivityControllerProvider).online) {
      return;
    }
    final probe = ref.read(networkProbeProvider);
    if (!await probe.onUnmeteredNetwork()) return;
    final snapshot = await ref.read(catalogSnapshotStoreProvider).load(tenant);
    if (snapshot == null || !ref.mounted || _tenant != tenant) return;

    final wanted = <String>{
      for (final product in snapshot.products)
        if ((product['imagen_principal'] as Map?)?['secure_url']
            case final String url when url.isNotEmpty)
          url,
    };
    final database = ref.read(offlineDatabaseProvider);
    final dir = await _tenantDir(tenant);
    final stored = await database.catalogImages(tenant);

    // Limpieza: imágenes de productos que ya no están en el catálogo.
    final stale = stored.keys.where((url) => !wanted.contains(url)).toList();
    if (stale.isNotEmpty) {
      for (final url in stale) {
        try {
          await File(p.join(dir.path, stored[url]!)).delete();
        } catch (_) {}
      }
      await database.deleteCatalogImages(tenant, stale);
    }

    // También se reintenta si el archivo fue borrado del disco.
    final missing = <String>[
      for (final url in wanted)
        if (!stored.containsKey(url) ||
            !File(p.join(dir.path, stored[url]!)).existsSync())
          url,
    ];
    if (!ref.mounted || _tenant != tenant) return;
    state = state.copyWith(
      paths: {
        for (final entry in stored.entries)
          if (wanted.contains(entry.key))
            entry.key: p.join(dir.path, entry.value),
      },
      missing: missing.length,
      downloading: missing.isNotEmpty,
      clearError: true,
    );
    if (missing.isEmpty) return;

    await dir.create(recursive: true);
    final dio = ref.read(catalogImageDioProvider);
    var failures = 0;
    var cursor = 0;
    Future<void> worker() async {
      while (cursor < missing.length) {
        if (!ref.mounted || _tenant != tenant) return;
        final url = missing[cursor++];
        try {
          final fileName = await _fetch(dio, url, dir);
          final path = p.join(dir.path, fileName);
          await database.putCatalogImage(
            tenant,
            url,
            fileName,
            await File(path).length(),
          );
          if (!ref.mounted || _tenant != tenant) return;
          state = state.copyWith(
            paths: {...state.paths, url: path},
            missing: state.missing - 1,
          );
        } catch (error) {
          failures++;
          developer.log('No se pudo guardar $url: $error', name: 'Images');
        }
      }
    }

    await Future.wait(List.generate(offlineImageConcurrency, (_) => worker()));
    if (!ref.mounted) return;
    if (failures > 0) _lastFailure = DateTime.now();
    state = state.copyWith(
      downloading: false,
      error: failures > 0 ? '$failures imágenes no se pudieron guardar' : null,
    );
  }

  /// Descarga a un archivo temporal y lo renombra al final: nunca queda una
  /// imagen a medio escribir con el nombre definitivo.
  static Future<String> _fetch(Dio dio, String url, Directory dir) async {
    final response = await dio.get<List<int>>(offlineImageUrl(url));
    final bytes = response.data ?? const <int>[];
    final type = response.headers.value(Headers.contentTypeHeader) ?? '';
    if (bytes.isEmpty || bytes.length > offlineImageMaxBytes) {
      throw StateError('Tamaño de imagen inválido: ${bytes.length} bytes');
    }
    if (type.isNotEmpty && !type.startsWith('image/')) {
      throw StateError('La respuesta no es una imagen: $type');
    }
    final fileName = offlineImageFileName(url);
    final temp = File(p.join(dir.path, '$fileName.part'));
    await temp.writeAsBytes(bytes, flush: true);
    await temp.rename(p.join(dir.path, fileName));
    return fileName;
  }
}
