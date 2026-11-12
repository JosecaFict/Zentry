import 'dart:io';

import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/features/offline/domain/offline_models.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final offlineSyncRepositoryProvider = Provider<OfflineSyncRepository>((ref) {
  return OfflineSyncRepository(ref.watch(dioProvider));
});

class OfflineSyncRepository {
  const OfflineSyncRepository(this._dio);

  final Dio _dio;

  Future<void> registerDevice({
    required String deviceId,
    required int branchId,
  }) async {
    try {
      await _dio.post(
        '/sync/devices',
        data: {
          'id_dispositivo': deviceId,
          'nombre': 'Zentry móvil · ${Platform.operatingSystem}',
          'plataforma': Platform.isIOS ? 'IOS' : 'ANDROID',
          'version_app': '1.0.0',
          'id_sucursal': branchId,
        },
      );
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<OfflineSnapshot> catalog(int branchId) async {
    try {
      final response = await _dio.get(
        '/sync/catalog',
        queryParameters: {'id_sucursal': branchId},
      );
      return OfflineSnapshot.fromJson(
        Map<String, dynamic>.from(response.data as Map),
      );
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<List<OfflineCustomer>> customers() async {
    try {
      final response = await _dio.get(
        '/customers',
        queryParameters: {'estado': 'ACTIVO'},
      );
      return (response.data as List<dynamic>? ?? const [])
          .map(
            (item) => OfflineCustomer.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(growable: false);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<Map<String, dynamic>> submitBatch({
    required String batchId,
    required String deviceId,
    required List<OfflineOperation> operations,
  }) async {
    try {
      final response = await _dio.post(
        '/sync/batches',
        data: {
          'id_lote': batchId,
          'id_dispositivo': deviceId,
          'fecha_cliente': DateTime.now().toUtc().toIso8601String(),
          'operaciones': operations
              .map(
                (operation) => {
                  'id_operacion': operation.id,
                  'tipo': operation.type == OfflineOperationType.sale
                      ? 'VENTA'
                      : 'RESERVA',
                  'fecha_cliente': operation.clientDate
                      .toUtc()
                      .toIso8601String(),
                  'payload': operation.payload,
                },
              )
              .toList(growable: false),
        },
      );
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  /// Cómo quedaron en el servidor operaciones propias (resueltas o no por un
  /// supervisor).
  Future<List<OfflineOperationServerStatus>> operationStatus(
    List<String> ids,
  ) async {
    if (ids.isEmpty) return const [];
    try {
      final response = await _dio.get<List<dynamic>>(
        '/sync/operations/status',
        queryParameters: {'ids': ids},
        options: Options(listFormat: ListFormat.multi),
      );
      return (response.data ?? const [])
          .map(
            (item) => OfflineOperationServerStatus.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(growable: false);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  /// Conflictos para encargados y administradores.
  Future<List<SyncConflict>> conflicts({String estado = 'PENDIENTE'}) async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/sync/conflicts',
        queryParameters: {'estado': estado},
      );
      return (response.data ?? const [])
          .map(
            (item) =>
                SyncConflict.fromJson(Map<String, dynamic>.from(item as Map)),
          )
          .toList(growable: false);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  /// [action]: `REAPLICAR` o `ANULAR` (este último exige [note]).
  Future<SyncConflict> resolveConflict(
    int conflictId, {
    required String action,
    String? note,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/sync/conflicts/$conflictId/resolve',
        data: {'accion': action, 'nota': ?note},
      );
      return SyncConflict.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<Map<String, dynamic>> confirmBatch({
    required String batchId,
    required String deviceId,
  }) async {
    try {
      final response = await _dio.post(
        '/sync/batches/$batchId/confirm',
        data: {'id_dispositivo': deviceId},
      );
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}
