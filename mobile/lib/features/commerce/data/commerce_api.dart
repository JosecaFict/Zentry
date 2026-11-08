import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/features/commerce/domain/commerce_models.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final commerceApiProvider = Provider<CommerceApi>((ref) {
  final dio = ref.watch(dioProvider);
  return CommerceApi(dio);
});

Map<String, dynamic> _asMap(dynamic data) {
  if (data is Map) {
    return Map<String, dynamic>.from(data);
  }
  return <String, dynamic>{};
}

class CommerceApi {
  final Dio _dio;

  CommerceApi(this._dio);

  // -------------------------------------------------------------
  // CARRITO DE COMPRAS (Regla: 1 Carrito = 1 Sucursal)
  // -------------------------------------------------------------
  Future<Cart> getCart() async {  // [CU-09] Consultar carrito activo
    try {
      final response = await _dio.get('/cart');
      return Cart.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Cart> addCartItem({  // [CU-09] Agregar prenda al carrito
    required int variantId,
    required int quantity,
    int? branchId,
  }) async {
    try {
      final response = await _dio.post(
        '/cart/items',
        data: {
          'id_variante': variantId,
          'cantidad': quantity,
          if (branchId != null) 'id_sucursal': branchId,
        },
      );
      return Cart.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Cart> updateCartItem({  // [CU-09] Modificar cantidad de prenda
    required int itemId,
    required int quantity,
  }) async {
    try {
      final response = await _dio.patch(
        '/cart/items/$itemId',
        data: {'cantidad': quantity},
      );
      return Cart.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Cart> removeCartItem({required int itemId}) async {  // [CU-09] Quitar prenda del carrito
    try {
      final response = await _dio.post('/cart/items/$itemId/remove');
      return Cart.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Cart> clearCart() async {  // [CU-09] Vaciar carrito de compras
    try {
      final response = await _dio.post('/cart/clear');
      return Cart.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // -------------------------------------------------------------
  // DIRECCIONES Y COTIZACIÓN DE ENVÍO (OpenRouteService)
  // -------------------------------------------------------------
  Future<List<Address>> listAddresses() async {  // [CU-09] Listar direcciones de entrega
    try {
      final response = await _dio.get('/addresses');
      final list = (response.data as List? ?? []);
      return list.map((e) => Address.fromJson(_asMap(e))).toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Address> createAddress({  // [CU-09] Registrar dirección de entrega
    required int cityId,
    String? alias,
    String? zone,
    required String address,
    String? reference,
    double? latitude,
    double? longitude,
    bool isMain = false,
  }) async {
    try {
      final response = await _dio.post(
        '/addresses',
        data: {
          'id_ciudad': cityId,
          if (alias != null && alias.isNotEmpty) 'alias': alias,
          if (zone != null && zone.isNotEmpty) 'zona': zone,
          'direccion': address,
          if (reference != null && reference.isNotEmpty) 'referencia': reference,
          if (latitude != null) 'latitud': latitude,
          if (longitude != null) 'longitud': longitude,
          'es_principal': isMain,
        },
      );
      return Address.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShippingQuote> quoteShipping({  // [CU-09] Cotizar flete de envío a domicilio
    required int branchId,
    required int addressId,
  }) async {
    try {
      final response = await _dio.post(
        '/shipping-quotes',
        data: {
          'id_sucursal': branchId,
          'id_direccion': addressId,
        },
      );
      return ShippingQuote.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // -------------------------------------------------------------
  // CHECKOUT Y PASARELA STRIPE
  // -------------------------------------------------------------
  Future<StripeCheckoutResponse> checkout({  // [CU-12] Iniciar checkout y pago con Stripe
    required int branchId,
    required String deliveryMode,
    int? addressId,
    int? quoteId,
    String? returnUrl,
  }) async {
    try {
      final response = await _dio.post(
        '/checkout',
        data: {
          'id_sucursal': branchId,
          'modalidad_entrega': deliveryMode,
          if (addressId != null) 'id_direccion': addressId,
          if (quoteId != null) 'id_cotizacion': quoteId,
          if (returnUrl != null) 'return_url': returnUrl,
        },
      );
      return StripeCheckoutResponse.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<StripeCheckoutStatusResponse> getCheckoutStatus(String sessionId) async {  // [CU-12] Consultar estado de sesión Stripe
    try {
      final response = await _dio.get('/checkout/$sessionId/status');
      return StripeCheckoutStatusResponse.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> cancelCheckout(String sessionId) async {  // [CU-12] Cancelar sesión de checkout
    try {
      await _dio.post('/checkout/$sessionId/cancel');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // -------------------------------------------------------------
  // RESERVAS DE PRENDAS
  // -------------------------------------------------------------
  Future<List<Reservation>> listReservations() async {  // [CU-10] Listar reservas del cliente
    try {
      final response = await _dio.get('/reservations');
      final list = (response.data as List? ?? []);
      return list.map((e) => Reservation.fromJson(_asMap(e))).toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Reservation> createReservation({  // [CU-10] Crear reserva presencial (48h)
    required int branchId,
    DateTime? appointmentDate,
    String? observation,
    required List<Map<String, dynamic>> items,
  }) async {
    try {
      final response = await _dio.post(
        '/reservations',
        data: {
          'id_sucursal': branchId,
          if (appointmentDate != null) 'fecha_cita': appointmentDate.toUtc().toIso8601String(),
          if (observation != null && observation.isNotEmpty) 'observacion': observation,
          'items': items,
        },
      );
      return Reservation.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Reservation> cancelReservation(int reservationId) async {  // [CU-10] Cancelar reserva presencial
    try {
      final response = await _dio.post('/reservations/$reservationId/cancel');
      return Reservation.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // -------------------------------------------------------------
  // PEDIDOS Y SEGUIMIENTO DEL CLIENTE
  // -------------------------------------------------------------
  Future<List<Order>> listOrders() async {  // [CU-13] Listar pedidos online
    try {
      final response = await _dio.get('/orders');
      final list = (response.data as List? ?? []);
      return list.map((e) => Order.fromJson(_asMap(e))).toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Order> getOrder(int orderId) async {  // [CU-13] Detalle de pedido online
    try {
      final response = await _dio.get('/orders/$orderId');
      return Order.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<Map<String, dynamic>>> listReturns() async {
    try {
      final response = await _dio.get('/returns');
      return (response.data as List? ?? [])
          .map((item) => _asMap(item))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> createReturn({
    required int saleId,
    required int detailId,
    required int quantity,
    required String kind,
    required String reason,
    int? requestedVariantId,
  }) async {
    try {
      await _dio.post('/returns', data: {
        'id_venta': saleId,
        'tipo_solicitud': kind,
        'motivo': reason,
        'items': [
          {'id_detalle_venta': detailId, 'cantidad': quantity, if (requestedVariantId != null) 'id_variante_solicitada': requestedVariantId},
        ],
      });
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<Map<String, dynamic>>> returnOptions(int saleId, int detailId, String kind) async {
    try {
      final response = await _dio.get('/returns/purchases/$saleId/items/$detailId/options', queryParameters: {'tipo_solicitud': kind});
      return (response.data as List? ?? []).map((item) => _asMap(item)).toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<Map<String, dynamic>>> listPurchases() async {
    try {
      final response = await _dio.get('/history/purchases');
      return (response.data as List? ?? []).map((item) => _asMap(item)).toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<int>> getOrderInvoicePdf(int orderId) async {  // [CU-12] Descargar factura en PDF
    try {
      final response = await _dio.get<List<int>>(
        '/orders/$orderId/invoice',
        options: Options(responseType: ResponseType.bytes),
      );
      return response.data ?? [];
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Order> confirmDelivery(int orderId) async {  // [CU-13] Confirmar entrega de pedido
    try {
      final response = await _dio.post('/orders/$orderId/confirm-delivery');
      return Order.fromJson(_asMap(response.data));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // -------------------------------------------------------------
  // NOTIFICACIONES OPERATIVAS
  // -------------------------------------------------------------
  Future<List<CustomerNotification>> listNotifications() async {  // [CU-20] Consultar bandeja de notificaciones
    try {
      final response = await _dio.get('/notifications');
      final list = (response.data as List? ?? []);
      return list.map((e) => CustomerNotification.fromJson(_asMap(e))).toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> registerDeviceToken({  // [CU-20] Registrar token de dispositivo FCM
    required String token,
    String platform = 'ios',
    String? deviceInfo,
  }) async {
    try {
      await _dio.post(
        '/notifications/devices',
        data: {
          'token': token.trim(),
          'plataforma': platform.trim().toLowerCase(),
          'dispositivo_info': deviceInfo?.trim(),
        },
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> markNotificationAsRead(int notificationId) async {  // [CU-20] Marcar notificación como leída
    try {
      await _dio.patch('/notifications/$notificationId/read');
    } on DioException {
      // Tolerar silenciosamente si el endpoint no responde o hay problemas de red
    }
  }

  Future<void> markAllNotificationsAsRead() async {  // [CU-20] Marcar todas como leídas
    try {
      await _dio.patch('/notifications/read-all');
    } on DioException {
      // Tolerar silenciosamente
    }
  }
}
