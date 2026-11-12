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
    this.acknowledgedAt,
    this.resolution,
    this.resolutionNote,
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

  /// Cuándo se revisó una operación fallida (null = alerta pendiente).
  final DateTime? acknowledgedAt;

  /// Cómo la resolvió un supervisor en el servidor: `REAPLICADA` o `ANULADA`.
  final String? resolution;
  final String? resolutionNote;

  bool get failed =>
      status == OfflineOperationStatus.conflict ||
      status == OfflineOperationStatus.rejected;

  /// Motivo del fallo en lenguaje claro, según el código del backend.
  String get failureReason => OfflineFailureReason.describe(errorCode);

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

/// Traduce los códigos de error de `/sync/batches` a mensajes para el vendedor.
abstract final class OfflineFailureReason {
  static String describe(String? code) => switch (code) {
    'STOCK_INSUFICIENTE' =>
      'No había stock: otra venta o reserva se registró antes.',
    'CONFLICTO_COMERCIAL' =>
      'Choca con otra operación (precio, reserva o estado del pedido).',
    'DATOS_INVALIDOS' => 'Faltan datos o no son válidos: revisa la operación.',
    'ERROR_INTERNO' =>
      'Error del servidor: vuelve a intentarlo o avisa a soporte.',
    _ => 'El servidor no aceptó la operación.',
  };
}

/// Operación rechazada o en conflicto pendiente de revisión, con el nombre
/// de las prendas para mostrarlo en la alerta.
class OfflineFailure {
  const OfflineFailure({
    required this.operation,
    required this.branchId,
    required this.items,
  });

  final OfflineOperation operation;
  final int branchId;

  /// Prendas de la operación, ej. "Polo básico M Negro".
  final List<String> items;

  String get title =>
      '${operation.label} no registrada'
      '${items.isEmpty ? '' : ' · ${items.join(', ')}'}';
}

/// Estado en el servidor de una operación fallida del dispositivo.
class OfflineOperationServerStatus {
  const OfflineOperationServerStatus({
    required this.id,
    required this.status,
    this.conflictStatus,
    this.action,
    this.note,
  });

  factory OfflineOperationServerStatus.fromJson(Map<String, dynamic> json) =>
      OfflineOperationServerStatus(
        id: json['id_operacion'] as String,
        status: json['estado'] as String,
        conflictStatus: json['conflicto_estado'] as String?,
        action: json['accion'] as String?,
        note: json['resolucion'] as String?,
      );

  final String id;
  final String status;
  final String? conflictStatus;

  /// `REAPLICADA` o `ANULADA` cuando un supervisor ya lo resolvió.
  final String? action;
  final String? note;

  bool get resolved => action != null;
}

class SyncConflictItem {
  const SyncConflictItem({
    required this.variantId,
    required this.quantity,
    required this.description,
  });

  factory SyncConflictItem.fromJson(Map<String, dynamic> json) =>
      SyncConflictItem(
        variantId: json['id_variante'] as int,
        quantity: json['cantidad'] as int,
        description: json['descripcion'] as String,
      );

  final int variantId;
  final int quantity;
  final String description;
}

/// Operación offline no registrada, vista por un encargado o administrador.
class SyncConflict {
  const SyncConflict({
    required this.id,
    required this.operationId,
    required this.operationType,
    required this.code,
    required this.status,
    required this.sellerId,
    required this.items,
    required this.clientDate,
    required this.createdAt,
    required this.canReapply,
    this.message,
    this.branchId,
    this.seller,
    this.totalCents,
    this.action,
    this.note,
    this.resolvedBy,
    this.resolvedAt,
  });

  factory SyncConflict.fromJson(Map<String, dynamic> json) => SyncConflict(
    id: json['id_conflicto'] as int,
    operationId: json['id_operacion'] as String,
    operationType: json['tipo_operacion'] as String,
    code: json['codigo'] as String,
    message: json['mensaje'] as String?,
    status: json['estado'] as String,
    branchId: json['id_sucursal'] as int?,
    sellerId: json['id_vendedor'] as int,
    seller: json['vendedor'] as String?,
    items: [
      for (final item in json['items'] as List<dynamic>? ?? const [])
        SyncConflictItem.fromJson(Map<String, dynamic>.from(item as Map)),
    ],
    totalCents: json['total_cobrado_centavos'] as int?,
    clientDate: DateTime.parse(json['fecha_cliente'] as String),
    createdAt: DateTime.parse(json['created_at'] as String),
    canReapply: json['puede_reaplicar'] as bool? ?? false,
    action: json['accion'] as String?,
    note: json['resolucion'] as String?,
    resolvedBy: json['resuelto_por'] as String?,
    resolvedAt: DateTime.tryParse(json['resuelto_at'] as String? ?? ''),
  );

  final int id;
  final String operationId;
  final String operationType;
  final String code;
  final String? message;

  /// `PENDIENTE`, `RESUELTO` o `DESCARTADO`.
  final String status;
  final int? branchId;
  final int sellerId;
  final String? seller;
  final List<SyncConflictItem> items;
  final int? totalCents;
  final DateTime clientDate;
  final DateTime createdAt;
  final bool canReapply;
  final String? action;
  final String? note;
  final String? resolvedBy;
  final DateTime? resolvedAt;

  bool get pending => status == 'PENDIENTE';
  String get label => operationType == 'VENTA' ? 'Venta' : 'Reserva';
  String get reason => OfflineFailureReason.describe(code);

  /// Qué le conviene hacer al supervisor según el motivo.
  String get advice => switch (code) {
    'STOCK_INSUFICIENTE' =>
      'Si la prenda sí estaba en la tienda, ajusta el inventario y reaplica. '
          'Si no, anúlala y registra cómo se resolvió con el cliente.',
    'CONFLICTO_COMERCIAL' =>
      'Revisa la reserva o el precio en conflicto; luego reaplica o anula.',
    'ERROR_INTERNO' => 'Fue un error del servidor: intenta reaplicarla.',
    'DATOS_INVALIDOS' =>
      'No se puede reaplicar tal cual. Anúlala; el vendedor puede volver a '
          'cargar la venta corregida.',
    _ => 'Revisa la operación y decide si reaplicarla o anularla.',
  };
}

/// Resultado de sincronizar la cola de una sucursal.
class OfflineSyncOutcome {
  const OfflineSyncOutcome({
    this.applied = 0,
    this.conflicts = 0,
    this.rejected = 0,
    this.batches = 0,
  });

  final int applied;
  final int conflicts;
  final int rejected;
  final int batches;

  bool get hasFailures => conflicts > 0 || rejected > 0;

  OfflineSyncOutcome operator +(OfflineSyncOutcome other) => OfflineSyncOutcome(
    applied: applied + other.applied,
    conflicts: conflicts + other.conflicts,
    rejected: rejected + other.rejected,
    batches: batches + other.batches,
  );

  String get summary =>
      'Sincronización lista: $applied aplicadas, $conflicts conflictos y '
      '$rejected rechazadas.';
}

/// La venta en línea no llegó al servidor (sin red o sin conexión con él):
/// es seguro guardarla en el teléfono para enviarla después, sin duplicarla.
class SaleNotSentException implements Exception {
  const SaleNotSentException();
}

/// Línea de una venta registrada en el servidor.
class RegisteredSaleLine {
  const RegisteredSaleLine({
    required this.description,
    required this.quantity,
    required this.subtotal,
  });

  factory RegisteredSaleLine.fromJson(Map<String, dynamic> json) =>
      RegisteredSaleLine(
        description: [
          json['producto'],
          json['talla'],
          json['color'],
        ].whereType<String>().where((part) => part.isNotEmpty).join(' '),
        quantity: (json['cantidad'] as num?)?.toInt() ?? 0,
        subtotal: double.tryParse('${json['subtotal']}') ?? 0,
      );

  final String description;
  final int quantity;
  final double subtotal;
}

/// Venta presencial registrada en el servidor (`POST /sales/pos`): lo que se
/// muestra al cajero como comprobante.
class RegisteredSale {
  const RegisteredSale({
    required this.id,
    required this.branch,
    required this.total,
    required this.date,
    required this.lines,
    this.customer,
    this.seller,
    this.paymentMethod,
    this.channel,
  });

  factory RegisteredSale.fromJson(Map<String, dynamic> json) => RegisteredSale(
    id: (json['id_venta'] as num).toInt(),
    branch: json['sucursal'] as String? ?? '',
    total: double.tryParse('${json['total']}') ?? 0,
    date:
        DateTime.tryParse(json['fecha_venta'] as String? ?? '')?.toLocal() ??
        DateTime.now(),
    lines: [
      for (final raw in json['items'] as List<dynamic>? ?? const [])
        RegisteredSaleLine.fromJson(Map<String, dynamic>.from(raw as Map)),
    ],
    customer: json['cliente_nombre'] as String?,
    seller: json['empleado_nombre'] as String?,
    paymentMethod: json['metodo_pago'] as String?,
    channel: json['canal_venta'] as String?,
  );

  final int id;
  final String branch;
  final double total;
  final DateTime date;
  final List<RegisteredSaleLine> lines;
  final String? customer;
  final String? seller;
  final String? paymentMethod;

  /// PRESENCIAL (en tienda) u ONLINE (pedido web).
  final String? channel;
}
