import 'dart:convert';

enum OfflineOperationType { sale, reservation }

enum OfflineOperationStatus {
  pending,
  sending,
  applied,
  conflict,
  rejected,
  confirmed;

  static OfflineOperationStatus fromApi(String value) => switch (value) {
    'ENVIANDO' => sending,
    'APLICADA' => applied,
    'CONFLICTO' => conflict,
    'RECHAZADA' => rejected,
    'CONFIRMADA' => confirmed,
    _ => pending,
  };

  String get apiValue => name.toUpperCase();
}

class OfflineScope {
  const OfflineScope({
    required this.tenantSlug,
    required this.userId,
    required this.branchId,
  });

  final String tenantSlug;
  final int userId;
  final int branchId;

  String get key => '$tenantSlug:$userId:$branchId';
}

class OfflineCatalogItem {
  const OfflineCatalogItem({
    required this.variantId,
    required this.sku,
    required this.product,
    required this.size,
    required this.color,
    required this.price,
    required this.physicalStock,
    required this.reservedStock,
    required this.availableStock,
    this.updatedAt,
  });

  factory OfflineCatalogItem.fromJson(Map<String, dynamic> json) =>
      OfflineCatalogItem(
        variantId: json['id_variante'] as int,
        sku: json['sku'] as String? ?? '',
        product: json['producto'] as String? ?? 'Prenda',
        size: json['talla'] as String? ?? '-',
        color: json['color'] as String? ?? '-',
        price: double.tryParse('${json['precio']}') ?? 0,
        physicalStock: int.tryParse('${json['stock_fisico']}') ?? 0,
        reservedStock: int.tryParse('${json['stock_reservado']}') ?? 0,
        availableStock: int.tryParse('${json['stock_disponible']}') ?? 0,
        updatedAt: DateTime.tryParse('${json['updated_at'] ?? ''}'),
      );

  final int variantId;
  final String sku;
  final String product;
  final String size;
  final String color;
  final double price;
  final int physicalStock;
  final int reservedStock;
  final int availableStock;
  final DateTime? updatedAt;
}

class OfflineCustomer {
  const OfflineCustomer({
    required this.id,
    required this.name,
    required this.email,
    this.phone,
  });

  factory OfflineCustomer.fromJson(Map<String, dynamic> json) =>
      OfflineCustomer(
        id: json['id_cliente'] as int,
        name:
            json['nombre_completo'] as String? ??
            'Cliente #${json['id_cliente']}',
        email: json['correo'] as String? ?? '',
        phone: json['telefono'] as String?,
      );

  final int id;
  final String name;
  final String email;
  final String? phone;
}

class OfflineSnapshot {
  const OfflineSnapshot({
    required this.branchId,
    required this.generatedAt,
    required this.version,
    required this.items,
  });

  factory OfflineSnapshot.fromJson(Map<String, dynamic> json) =>
      OfflineSnapshot(
        branchId: json['id_sucursal'] as int,
        generatedAt: DateTime.parse(json['generado_at'] as String),
        version: json['version'] as String,
        items: (json['items'] as List<dynamic>? ?? const [])
            .map(
              (item) => OfflineCatalogItem.fromJson(
                Map<String, dynamic>.from(item as Map),
              ),
            )
            .toList(growable: false),
      );

  final int branchId;
  final DateTime generatedAt;
  final String version;
  final List<OfflineCatalogItem> items;
}

class OfflineOperation {
  const OfflineOperation({
    required this.id,
    required this.type,
    required this.clientDate,
    required this.payload,
    required this.status,
    required this.attempts,
    required this.createdAt,
    this.errorCode,
    this.errorMessage,
    this.batchId,
    this.result,
  });

  final String id;
  final OfflineOperationType type;
  final DateTime clientDate;
  final Map<String, dynamic> payload;
  final OfflineOperationStatus status;
  final int attempts;
  final DateTime createdAt;
  final String? errorCode;
  final String? errorMessage;
  final String? batchId;
  final Map<String, dynamic>? result;

  String get label => type == OfflineOperationType.sale ? 'Venta' : 'Reserva';
  int get units => (payload['items'] as List<dynamic>? ?? const []).fold(
    0,
    (sum, item) => sum + ((item as Map)['cantidad'] as int? ?? 0),
  );

  static Map<String, dynamic> decodeMap(String? value) {
    if (value == null || value.isEmpty) return <String, dynamic>{};
    return Map<String, dynamic>.from(jsonDecode(value) as Map);
  }
}

class SyncBatchResult {
  const SyncBatchResult({
    required this.batchId,
    required this.applied,
    required this.conflicts,
    required this.rejected,
  });

  final String batchId;
  final int applied;
  final int conflicts;
  final int rejected;
}
