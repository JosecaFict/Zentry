import 'dart:async';

import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/commerce/data/commerce_api.dart';
import 'package:capricho_store/features/commerce/domain/commerce_models.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_dialogs.dart';
import 'package:capricho_store/shared/widgets/location_map_preview.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  String _deliveryMode = 'RETIRO_SUCURSAL'; // 'RETIRO_SUCURSAL' | 'DELIVERY'
  Address? _selectedAddress;
  ShippingQuote? _shippingQuote;
  bool _quoting = false;
  bool _processingCheckout = false;
  String? _error;

  final _currency = NumberFormat.currency(locale: 'es_BO', symbol: 'Bs ');

  @override
  void initState() {
    super.initState();
    // Cargar direcciones
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initDefaultAddress();
    });
  }

  Future<void> _initDefaultAddress() async {
    final addresses = await ref.read(addressesProvider.future);
    if (addresses.isNotEmpty && mounted) {
      final mainAddress = addresses.firstWhere(
        (a) => a.esPrincipal,
        orElse: () => addresses.first,
      );
      setState(() => _selectedAddress = mainAddress);
    }
  }

  Future<void> _onDeliveryModeChanged(String mode) async {
    HapticFeedback.selectionClick();
    setState(() {
      _deliveryMode = mode;
      _error = null;
    });

    if (mode == 'DELIVERY' && _selectedAddress != null) {
      await _requestQuote(_selectedAddress!);
    }
  }

  Future<void> _selectAddress(Address address) async {
    HapticFeedback.selectionClick();
    setState(() {
      _selectedAddress = address;
      _error = null;
    });
    await _requestQuote(address);
  }

  Future<void> _requestQuote(Address address) async {
    final cart = ref.read(cartProvider).value;
    if (cart == null || cart.idSucursal == null) return;

    setState(() {
      _quoting = true;
      _shippingQuote = null;
    });

    try {
      final api = ref.read(commerceApiProvider);
      final quote = await api.quoteShipping(
        branchId: cart.idSucursal!,
        addressId: address.idDireccion,
      );
      if (mounted) {
        setState(() {
          _shippingQuote = quote;
          _quoting = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _quoting = false;
          _error = 'Error cotizando envío: ${e.toString().replaceAll("ApiException: ", "")}';
        });
      }
    }
  }

  Future<void> _showNewAddressDialog() async {
    final aliasController = TextEditingController();
    final streetController = TextEditingController();
    final zoneController = TextEditingController(text: 'Centro');
    final refController = TextEditingController();
    double selectedLat = -17.7833;
    double selectedLng = -63.1821;
    String? selectedZone = 'Centro';
    bool isSaving = false;

    const sczZones = [
      {'name': 'Centro', 'lat': -17.7833, 'lng': -63.1821},
      {'name': 'Equipetrol', 'lat': -17.7680, 'lng': -63.1950},
      {'name': 'Urbarí', 'lat': -17.7950, 'lng': -63.1980},
      {'name': 'Las Palmas', 'lat': -17.8050, 'lng': -63.2080},
      {'name': 'Norte / Banzer', 'lat': -17.7400, 'lng': -63.1800},
      {'name': 'Plan 3000', 'lat': -17.8250, 'lng': -63.1350},
    ];

    await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) => AlertDialog(
          insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(
            children: [
              Icon(Icons.add_location_alt_rounded, color: AppColors.cobalt),
              SizedBox(width: 8),
              Text('Dirección de entrega', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            ],
          ),
          content: SizedBox(
            width: MediaQuery.of(context).size.width,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: aliasController,
                    decoration: const InputDecoration(
                      labelText: 'Nombre / Alias (ej. Casa, Trabajo, Depa)',
                      hintText: 'Ej. Casa de campo',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: streetController,
                    decoration: const InputDecoration(
                      labelText: 'Calle y número *',
                      hintText: 'Ej. Av. San Martín #450',
                    ),
                  ),
                  const SizedBox(height: 14),
                  const Text(
                    'Zonas rápidas de Santa Cruz (GPS):',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.inkSoft),
                  ),
                  const SizedBox(height: 6),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: sczZones.map((z) {
                        final isSelected = selectedZone == z['name'];
                        return Padding(
                          padding: const EdgeInsets.only(right: 6),
                          child: ChoiceChip(
                            label: Text(z['name'] as String, style: const TextStyle(fontSize: 12)),
                            selected: isSelected,
                            selectedColor: AppColors.cobaltLight,
                            onSelected: (val) {
                              if (val) {
                                setModalState(() {
                                  selectedZone = z['name'] as String;
                                  zoneController.text = z['name'] as String;
                                  selectedLat = z['lat'] as double;
                                  selectedLng = z['lng'] as double;
                                });
                              }
                            },
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: zoneController,
                    decoration: const InputDecoration(
                      labelText: 'Zona / Barrio *',
                      hintText: 'Ej. Centro',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: refController,
                    decoration: const InputDecoration(
                      labelText: 'Referencia (opcional)',
                      hintText: 'Ej. Frente a la plaza, portón blanco',
                    ),
                  ),
                  const SizedBox(height: 14),
                  const Text(
                    'Mapa de ubicación (arrastra para ajustar el pin):',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.inkSoft),
                  ),
                  const SizedBox(height: 8),
                  LocationMapPreview(
                    latitude: selectedLat,
                    longitude: selectedLng,
                    zone: selectedZone ?? zoneController.text,
                    height: 200,
                    onLocationChanged: (coords) {
                      setModalState(() {
                        selectedLat = coords.lat;
                        selectedLng = coords.lng;
                      });
                    },
                    onAddressDetected: (geo) {
                      setModalState(() {
                        if (geo.road != null && geo.road!.isNotEmpty) {
                          streetController.text = geo.road!;
                        }
                        if (geo.zone != null && geo.zone!.isNotEmpty) {
                          zoneController.text = geo.zone!;
                          selectedZone = geo.zone;
                        }
                      });
                    },
                  ),
                ],
              ),
            ),
          ),
          actions: [
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: isSaving ? null : () => Navigator.of(ctx).pop(false),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: const Text('Cancelar'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  flex: 2,
                  child: FilledButton(
                    onPressed: isSaving
                        ? null
                        : () async {
                            if (streetController.text.trim().isEmpty ||
                                zoneController.text.trim().isEmpty) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Por favor completa la calle y la zona')),
                              );
                              return;
                            }
                            setModalState(() => isSaving = true);
                            HapticFeedback.selectionClick();
                            try {
                              final newAddr = await ref.read(addressesProvider.notifier).addAddress(
                                    cityId: 1,
                                    alias: aliasController.text.trim().isNotEmpty
                                        ? aliasController.text.trim()
                                        : null,
                                    zone: zoneController.text.trim(),
                                    address: streetController.text.trim(),
                                    reference: refController.text.trim().isNotEmpty
                                        ? refController.text.trim()
                                        : null,
                                    latitude: selectedLat,
                                    longitude: selectedLng,
                                    isMain: true,
                                  );
                              if (ctx.mounted) {
                                Navigator.of(ctx).pop(true);
                              }
                              // Sincronizar con la lista fresca de direcciones y cotizar de inmediato
                              final updatedList = await ref.read(addressesProvider.future);
                              final created = updatedList.firstWhere(
                                (a) => a.idDireccion == newAddr.idDireccion,
                                orElse: () => newAddr,
                              );
                              if (mounted) {
                                setState(() => _selectedAddress = created);
                                await _requestQuote(created);
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text('Dirección "${created.displayName}" agregada y seleccionada'),
                                    backgroundColor: AppColors.success,
                                  ),
                                );
                              }
                            } catch (e) {
                              if (ctx.mounted) {
                                setModalState(() => isSaving = false);
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text('Error al crear dirección: $e')),
                                );
                              }
                            }
                          },
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.cobalt,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: isSaving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('Guardar y cotizar'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _startStripeCheckout(Cart cart) async {
    final branchId = cart.idSucursal ?? (_shippingQuote?.idSucursal ?? 1);

    if (_deliveryMode == 'DELIVERY') {
      if (_selectedAddress == null) {
        const msg = 'Por favor selecciona una dirección de entrega.';
        setState(() => _error = msg);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text(msg)));
        return;
      }
      if (_shippingQuote == null) {
        const msg = 'Falta cotizar el envío para esta dirección.';
        setState(() => _error = msg);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text(msg)));
        return;
      }
    }

    setState(() {
      _processingCheckout = true;
      _error = null;
    });

    HapticFeedback.mediumImpact();

    try {
      debugPrint('[Checkout] Iniciando checkout en sucursal $branchId, modalidad $_deliveryMode');
      final api = ref.read(commerceApiProvider);
      final checkoutData = await api.checkout(
        branchId: branchId,
        deliveryMode: _deliveryMode,
        addressId: _deliveryMode == 'DELIVERY' ? _selectedAddress?.idDireccion : null,
        quoteId: _deliveryMode == 'DELIVERY' ? _shippingQuote?.idCotizacion : null,
        returnUrl: 'https://zentrysaas.store?source=mobile',
      );

      debugPrint('[Checkout] Sesión creada: ${checkoutData.sessionId}, url: ${checkoutData.checkoutUrl}');
      final uri = Uri.parse(checkoutData.checkoutUrl);

      // Mostrar el sondeo y estado de verificación antes de abrir Safari
      // El temporizador de fondo detectará el pago y cerrará Safari automáticamente vía closeInAppWebView()
      if (mounted) {
        _showPaymentVerificationSheet(checkoutData.sessionId);
      }

      bool launched = false;
      try {
        launched = await launchUrl(
          uri,
          mode: LaunchMode.inAppBrowserView,
        );
      } catch (e) {
        debugPrint('[Checkout] inAppBrowserView falló ($e), reintentando con externalApplication');
        launched = false;
      }

      if (!launched) {
        try {
          launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
        } catch (e) {
          debugPrint('[Checkout] externalApplication falló: $e');
          launched = false;
        }
      }

      if (!launched && mounted) {
        Navigator.of(context, rootNavigator: true).pop();
        const msg = 'No se pudo abrir la pasarela de pago en el navegador de tu iPhone.';
        setState(() {
          _error = msg;
          _processingCheckout = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text(msg), backgroundColor: AppColors.danger),
        );
        return;
      }
    } catch (e) {
      debugPrint('[Checkout] Error en api.checkout: $e');
      if (mounted) {
        final cleanError = e.toString().replaceAll('ApiException: ', '');
        setState(() {
          _error = cleanError;
          _processingCheckout = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(cleanError),
            backgroundColor: AppColors.danger,
            duration: const Duration(seconds: 8),
            action: SnackBarAction(
              label: 'OK',
              textColor: Colors.white,
              onPressed: () {},
            ),
          ),
        );
      }
    }
  }

  void _showPaymentVerificationSheet(String sessionId) {
    showModalBottomSheet(
      context: context,
      isDismissible: false,
      enableDrag: false,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => _PaymentPollerView(
        sessionId: sessionId,
        onSuccess: (order, receiptUrl) {
          Navigator.of(ctx).pop();
          ref.read(cartProvider.notifier).refresh();
          ref.read(ordersProvider.notifier).refresh();
          _showSuccessScreen(order, receiptUrl);
        },
        onCancel: ([reason]) {
          Navigator.of(ctx).pop();
          setState(() {
            _processingCheckout = false;
            if (reason != null && reason.isNotEmpty) {
              _error = reason;
            }
          });
        },
      ),
    );
  }

  void _showSuccessScreen(Order order, String? receiptUrl) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        contentPadding: const EdgeInsets.fromLTRB(22, 26, 22, 24),
        content: SizedBox(
          width: MediaQuery.of(context).size.width,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check_circle_rounded,
                  color: AppColors.success,
                  size: 54,
                ),
              ),
              const SizedBox(height: 18),
              const Text(
                '¡Pedido Confirmado!',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Orden #${order.idPedido} registrada exitosamente.',
                style: const TextStyle(fontSize: 13, color: AppColors.inkSoft),
              ),
              const SizedBox(height: 14),
              Text(
                'Total pagado: ${_currency.format(order.total)}',
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 17,
                  color: AppColors.cobaltDark,
                ),
              ),
              const SizedBox(height: 24),

              // Botones simétricos y encuadrados al 100% de ancho
              if (receiptUrl != null && receiptUrl.isNotEmpty) ...[
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => launchUrl(
                      Uri.parse(receiptUrl),
                      mode: LaunchMode.inAppBrowserView,
                    ),
                    icon: const Icon(Icons.receipt_long_rounded, size: 18, color: AppColors.cobalt),
                    label: const Text(
                      'Ver recibo de Stripe',
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.cobalt,
                      side: const BorderSide(color: AppColors.cobalt, width: 1.5),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
              ],
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    context.go('/pedidos');
                  },
                  icon: const Icon(Icons.shopping_bag_outlined, size: 18),
                  label: const Text(
                    'Ir a mis pedidos',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                  ),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.cobalt,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartProvider).value;

    if (cart == null || cart.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: const Text('Confirmar pedido')),
        body: const Center(
          child: Text('No hay productos en el carrito para procesar.'),
        ),
      );
    }

    final shippingCost = _deliveryMode == 'DELIVERY'
        ? (_shippingQuote?.costoEstimado ?? 0.0)
        : 0.0;
    final grandTotal = cart.total + shippingCost;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded),
          tooltip: 'Atrás',
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/carrito');
            }
          },
        ),
        title: const Text('Confirmar pedido'),
        shape: const Border(
          bottom: BorderSide(color: AppColors.line, width: 1),
        ),
      ),
      body: Stack(
        children: [
          ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 140),
            children: [
              // Selector de Modalidad de Entrega
              const Text(
                'Modalidad de Entrega',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: _buildDeliveryTypeOption(
                      title: 'Retiro en Tienda',
                      subtitle: 'Sin costo adicional',
                      icon: Icons.store_mall_directory_rounded,
                      isSelected: _deliveryMode == 'RETIRO_SUCURSAL',
                      onTap: () => _onDeliveryModeChanged('RETIRO_SUCURSAL'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildDeliveryTypeOption(
                      title: 'Envío Delivery',
                      subtitle: 'A tu domicilio',
                      icon: Icons.two_wheeler_rounded,
                      isSelected: _deliveryMode == 'DELIVERY',
                      onTap: () => _onDeliveryModeChanged('DELIVERY'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Contenido según modalidad
              if (_deliveryMode == 'RETIRO_SUCURSAL')
                _buildPickupSection(cart)
              else
                _buildDeliverySection(),

              const SizedBox(height: 24),

              // Resumen financiero
              const Text(
                'Resumen de la orden',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppColors.line),
                ),
                child: Column(
                  children: [
                    _buildSummaryRow(
                      'Subtotal prendas (${cart.totalQuantity})',
                      _currency.format(cart.total),
                    ),
                    const SizedBox(height: 8),
                    _buildSummaryRow(
                      'Costo de envío',
                      _deliveryMode == 'RETIRO_SUCURSAL'
                          ? 'Gratis (Bs 0.00)'
                          : (_shippingQuote != null
                              ? _currency.format(_shippingQuote!.costoEstimado)
                              : (_quoting ? 'Calculando...' : 'Pendiente')),
                      highlight: _deliveryMode == 'RETIRO_SUCURSAL',
                    ),
                    const Divider(height: 20),
                    _buildSummaryRow(
                      'Total a pagar',
                      _currency.format(grandTotal),
                      isTotal: true,
                    ),
                  ],
                ),
              ),

              if (_error != null) ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.danger.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    _error!,
                    style: const TextStyle(
                      color: AppColors.danger,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ],
          ),

          // Barra inferior de Pago
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: const Border(top: BorderSide(color: AppColors.line, width: 1)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.06),
                    blurRadius: 10,
                    offset: const Offset(0, -4),
                  ),
                ],
              ),
              child: SafeArea(
                top: false,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  child: FilledButton.icon(
                    onPressed: _processingCheckout ? null : () => _startStripeCheckout(cart),
                    icon: _processingCheckout
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.payment_rounded),
                    label: Text(
                      _processingCheckout
                          ? 'Conectando con Stripe…'
                          : 'Pagar ${_currency.format(grandTotal)} con Stripe',
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 15,
                      ),
                    ),
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.cobalt,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDeliveryTypeOption({
    required String title,
    required String subtitle,
    required IconData icon,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.cobaltLight : AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? AppColors.cobalt : AppColors.line,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              icon,
              color: isSelected ? AppColors.cobalt : AppColors.inkSoft,
              size: 26,
            ),
            const SizedBox(height: 8),
            Text(
              title,
              style: TextStyle(
                fontWeight: FontWeight.w800,
                fontSize: 14,
                color: isSelected ? AppColors.cobaltDark : AppColors.ink,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              style: TextStyle(
                fontSize: 11.5,
                color: isSelected ? AppColors.cobalt : AppColors.inkSoft,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPickupSection(Cart cart) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.check_circle_rounded,
                  color: AppColors.success, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Retiro en Sucursal ${cart.sucursal ?? ""}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 14.5,
                    color: AppColors.ink,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Tu pedido se preparará y estará disponible para entrega inmediata tras la confirmación del pago.',
            style: TextStyle(fontSize: 13, color: AppColors.inkSoft, height: 1.35),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.canvas,
              borderRadius: BorderRadius.circular(6),
            ),
            child: const Text(
              'Costo de entrega: Bs 0.00 (Gratuito)',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 12,
                color: AppColors.success,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDeliverySection() {
    final addressesAsync = ref.watch(addressesProvider);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Dirección de Envío',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 14.5,
                  color: AppColors.ink,
                ),
              ),
              TextButton.icon(
                onPressed: _showNewAddressDialog,
                icon: const Icon(Icons.add_rounded, size: 16),
                label: const Text('Nueva'),
              ),
            ],
          ),
          const SizedBox(height: 8),
          addressesAsync.when(
            loading: () => const LinearProgressIndicator(),
            error: (err, _) => Text('Error: $err'),
            data: (addresses) {
              if (addresses.isEmpty) {
                return OutlinedButton.icon(
                  onPressed: _showNewAddressDialog,
                  icon: const Icon(Icons.add_location_alt_outlined),
                  label: const Text('Registrar dirección para delivery'),
                );
              }
              final selected = addresses.firstWhere(
                (a) => a.idDireccion == _selectedAddress?.idDireccion,
                orElse: () => addresses.firstWhere(
                  (a) => a.esPrincipal,
                  orElse: () => addresses.first,
                ),
              );

              // Sincronizar _selectedAddress si aún no está configurado
              if (_selectedAddress?.idDireccion != selected.idDireccion) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted) {
                    setState(() => _selectedAddress = selected);
                    if (_shippingQuote == null && _deliveryMode == 'DELIVERY') {
                      _requestQuote(selected);
                    }
                  }
                });
              }

              return DropdownButtonFormField<int>(
                value: selected.idDireccion,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Selecciona dirección guardada',
                  border: OutlineInputBorder(),
                ),
                items: addresses
                    .map(
                      (addr) => DropdownMenuItem<int>(
                        value: addr.idDireccion,
                        child: Row(
                          children: [
                            Icon(
                              Icons.location_on_rounded,
                              size: 16,
                              color: addr.latitud != null ? AppColors.cobalt : AppColors.inkSoft,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                addr.displayName,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            if (addr.latitud != null && addr.longitud != null)
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFEFF6FF),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Text(
                                  'GPS OK',
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w800,
                                    color: AppColors.cobaltDark,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (int? newId) {
                  if (newId != null) {
                    final chosen = addresses.firstWhere((a) => a.idDireccion == newId);
                    _selectAddress(chosen);
                  }
                },
              );
            },
          ),
          const SizedBox(height: 14),

          // Tarjeta de Cotización OpenRouteService
          if (_quoting)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Row(
                children: [
                  SizedBox(
                    height: 16,
                    width: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text('Cotizando ruta vial con OpenRouteService...'),
                  ),
                ],
              ),
            )
          else if (_shippingQuote != null)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.canvas,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.line),
              ),
              child: Row(
                children: [
                  const Icon(Icons.route_rounded,
                      color: AppColors.cobalt, size: 22),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Distancia: ${_shippingQuote!.formattedDistance} (${_shippingQuote!.duracionEstimadaMin ?? 15} min aprox.)',
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 12.5,
                            color: AppColors.ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        const Text(
                          'Cálculo vial en tiempo real vía OpenRouteService',
                          style: TextStyle(fontSize: 11, color: AppColors.inkSoft),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    _shippingQuote!.formattedCost,
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 15,
                      color: AppColors.cobaltDark,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSummaryRow(
    String label,
    String value, {
    bool isTotal = false,
    bool highlight = false,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: isTotal ? 16 : 13.5,
            fontWeight: isTotal ? FontWeight.w800 : FontWeight.w500,
            color: isTotal ? AppColors.ink : AppColors.inkSoft,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            fontSize: isTotal ? 18 : 13.5,
            fontWeight: isTotal ? FontWeight.w900 : FontWeight.w700,
            color: isTotal
                ? AppColors.cobaltDark
                : (highlight ? AppColors.success : AppColors.ink),
          ),
        ),
      ],
    );
  }
}

enum _PollerPhase { verifying, success, failed }

class _PaymentPollerView extends StatefulWidget {
  final String sessionId;
  final void Function(Order order, String? receiptUrl) onSuccess;
  final void Function([String? reason]) onCancel;

  const _PaymentPollerView({
    required this.sessionId,
    required this.onSuccess,
    required this.onCancel,
  });

  @override
  State<_PaymentPollerView> createState() => _PaymentPollerViewState();
}

class _PaymentPollerViewState extends State<_PaymentPollerView> {
  Timer? _timer;
  _PollerPhase _phase = _PollerPhase.verifying;
  String _statusMessage = 'Esperando confirmación segura de Stripe...';

  @override
  void initState() {
    super.initState();
    _startPolling();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _timer = Timer.periodic(const Duration(seconds: 2), (t) async {
      final container = ProviderScope.containerOf(context, listen: false);
      final api = container.read(commerceApiProvider);

      try {
        final status = await api.getCheckoutStatus(widget.sessionId);
        if (!mounted) return;

        if (status.status == 'PAGADO') {
          t.cancel();
          // Cerrar automáticamente la ventana interna del navegador de Stripe
          try {
            await closeInAppWebView();
          } catch (_) {}
          if (defaultTargetPlatform == TargetPlatform.android) {
            try {
              const channel = MethodChannel('com.capricho.store/body_pose');
              await channel.invokeMethod('bringToFront');
            } catch (_) {}
          }

          if (!mounted) return;
          setState(() {
            _phase = _PollerPhase.success;
            _statusMessage = '¡Pago confirmado con éxito!';
          });

          // Breve animación para mostrar el estado completado antes de navegar
          Future.delayed(const Duration(milliseconds: 1400), () {
            if (!mounted) return;
            if (status.order != null) {
              widget.onSuccess(status.order!, status.receiptUrl);
            } else {
              Navigator.of(context).pop();
              final c = ProviderScope.containerOf(context, listen: false);
              c.read(cartProvider.notifier).refresh();
              c.read(ordersProvider.notifier).refresh();
              context.go('/pedidos');
            }
          });
        } else if (status.status == 'CANCELADO' || status.status == 'RECHAZADO') {
          t.cancel();
          try {
            await closeInAppWebView();
          } catch (_) {}
          if (defaultTargetPlatform == TargetPlatform.android) {
            try {
              const channel = MethodChannel('com.capricho.store/body_pose');
              await channel.invokeMethod('bringToFront');
            } catch (_) {}
          }

          if (!mounted) return;
          setState(() {
            _phase = _PollerPhase.failed;
            _statusMessage = status.message.isNotEmpty
                ? status.message
                : 'El pago fue cancelado o rechazado por la pasarela.';
          });
        } else {
          setState(() {
            _statusMessage = status.message.isNotEmpty
                ? status.message
                : 'Procesando pago con Stripe...';
          });
        }
      } catch (e) {
        if (!mounted) return;
        debugPrint('[StripePoller] Error: $e');
        setState(() {
          final errStr = e.toString().replaceAll('ApiException: ', '').trim();
          _statusMessage = errStr.isNotEmpty ? errStr : 'Confirmando estado con Stripe...';
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 32),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (_phase == _PollerPhase.verifying) ...[
              const CircularProgressIndicator(color: AppColors.cobalt),
              const SizedBox(height: 18),
              const Text(
                'Verificando tu pago con Stripe',
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _statusMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 13, color: AppColors.inkSoft),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  OutlinedButton(
                    onPressed: () {
                      try {
                        closeInAppWebView();
                      } catch (_) {}
                      widget.onCancel();
                    },
                    child: const Text('Volver al checkout'),
                  ),
                  const SizedBox(width: 10),
                  FilledButton.tonal(
                    onPressed: () {
                      try {
                        closeInAppWebView();
                      } catch (_) {}
                      Navigator.of(context).pop();
                      final c = ProviderScope.containerOf(context, listen: false);
                      c.read(cartProvider.notifier).refresh();
                      c.read(ordersProvider.notifier).refresh();
                      context.go('/pedidos');
                    },
                    child: const Text('Ver Mis Pedidos'),
                  ),
                ],
              ),
            ] else if (_phase == _PollerPhase.success) ...[
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check_circle_rounded,
                  color: AppColors.success,
                  size: 52,
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                '¡Pago Completado!',
                style: TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _statusMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w600,
                  color: AppColors.success,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Cargando los detalles de tu compra...',
                style: TextStyle(fontSize: 12, color: AppColors.inkSoft),
              ),
            ] else if (_phase == _PollerPhase.failed) ...[
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.danger.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.cancel_rounded,
                  color: AppColors.danger,
                  size: 52,
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Pago No Completado',
                style: TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _statusMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 13, color: AppColors.inkSoft),
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: () => widget.onCancel(_statusMessage),
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.ink,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                child: const Text('Volver al checkout'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
