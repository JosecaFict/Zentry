import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/catalog/data/catalog_repository.dart';
import 'package:capricho_store/features/catalog/data/catalog_source.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/features/commerce/presentation/reservation_bottom_sheet.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_dialogs.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_image.dart';
import 'package:capricho_store/shared/widgets/message_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

/// [CU-04 / CU-18] Pantalla de Detalle de Prenda y Botón de Probador AR
class ProductDetailScreen extends ConsumerStatefulWidget {
  const ProductDetailScreen({
    required this.productId,
    this.branchId,
    super.key,
  });
  final int productId;
  final int? branchId;

  @override
  ConsumerState<ProductDetailScreen> createState() =>
      _ProductDetailScreenState();
}

class _ProductDetailScreenState extends ConsumerState<ProductDetailScreen> {
  late Future<_ProductDetailData> _future;
  final PageController _imagePageController = PageController();

  int _selectedImageIndex = 0;
  String? _selectedSize;
  String? _selectedColor;
  int? _selectedBranchId;
  int _quantity = 1;
  bool _addingToCart = false;

  @override
  void initState() {
    super.initState();
    _selectedBranchId = widget.branchId;
    _loadData();
  }

  @override
  void dispose() {
    _imagePageController.dispose();
    super.dispose();
  }

  void _loadData() {
    final repo = ref.read(catalogRepositoryProvider);
    _future =
        Future.wait([
          repo.product(widget.productId, branchId: _selectedBranchId),
          repo
              .productImages(widget.productId)
              .catchError((_) => <ProductImage>[]),
          repo
              .productVariants(
                widget.productId,
                branchId: _selectedBranchId,
              )
              .catchError((_) => <ProductVariant>[]),
          repo
              .productMeasurements(widget.productId)
              .catchError((_) => <ProductMeasurement>[]),
          repo.branches().catchError((_) => <BranchItem>[]),
        ]).then((results) {
          final product = results[0] as Product;
          final images = results[1] as List<ProductImage>;
          final variants = results[2] as List<ProductVariant>;
          final measurements = results[3] as List<ProductMeasurement>;
          final branches = results[4] as List<BranchItem>;

          // Si no devolvió imágenes específicas, usamos la principal del producto
          final effectiveImages = images.isNotEmpty
              ? images
              : (product.image != null ? [product.image!] : <ProductImage>[]);

          // Si el endpoint de variantes dio vacío, usar las que vienen anidadas en product
          final effectiveVariants = variants.isNotEmpty
              ? variants
              : product.variants;

          return _ProductDetailData(
            product: product,
            images: effectiveImages,
            variants: effectiveVariants,
            measurements: measurements,
            branches: branches,
          );
        });
  }

  Future<void> _refresh() async {
    setState(() {
      _loadData();
    });
    await _future;
  }

  ProductVariant? _findMatchingVariant(List<ProductVariant> variants) {
    if (_selectedSize == null && _selectedColor == null) return null;
    try {
      return variants.firstWhere((v) {
        final matchesSize = _selectedSize == null || v.size == _selectedSize;
        final matchesColor =
            _selectedColor == null || v.color == _selectedColor;
        return matchesSize && matchesColor;
      });
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    refreshCatalogOnReconnect(ref, () => setState(_loadData));
    final currency = NumberFormat.currency(locale: 'es_BO', symbol: 'Bs.');
    final cartCount = ref.watch(cartItemCountProvider);

    return FutureBuilder<_ProductDetailData>(
      future: _future,
      builder: (context, snapshot) {
        final appBar = AppBar(
          title: const Text('Detalle de prenda'),
          shape: const Border(
            bottom: BorderSide(color: AppColors.line, width: 1),
          ),
          actions: [
            IconButton(
              tooltip: 'Actualizar',
              icon: const Icon(Icons.refresh_rounded),
              onPressed: _refresh,
            ),
            IconButton(
              tooltip: 'Ver Carrito',
              icon: Badge(
                isLabelVisible: cartCount > 0,
                label: Text('$cartCount'),
                backgroundColor: AppColors.cobalt,
                child: const Icon(Icons.shopping_bag_outlined),
              ),
              onPressed: () => context.go('/carrito'),
            ),
            const SizedBox(width: 4),
          ],
        );

        if (snapshot.connectionState == ConnectionState.waiting) {
          return Scaffold(
            appBar: appBar,
            body: const Center(child: CircularProgressIndicator()),
          );
        }

        if (snapshot.hasError) {
          return Scaffold(
            appBar: appBar,
            body: MessageState(
              title: 'No pudimos cargar la prenda',
              message: snapshot.error.toString(),
              onRetry: _refresh,
            ),
          );
        }

        final data = snapshot.data!;
        final product = data.product;
        final images = data.images;
        final variants = data.variants;
        final measurements = data.measurements;
        final branches = data.branches;
        final visibleImages = _imagesForSelectedColor(images, variants);
        final visibleSizes = variants
            .where(
              (variant) =>
                  variant.active &&
                  (_selectedColor == null || variant.color == _selectedColor),
            )
            .map((variant) => variant.size)
            .toSet()
            .toList();

        final matchedVariant = _findMatchingVariant(variants);

        return Scaffold(
          appBar: appBar,
          body: RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.only(bottom: 120),
              children: [
                _buildImageGallery(visibleImages),
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Marca y Público
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            product.brand.toUpperCase(),
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 1.2,
                              color: AppColors.cobalt,
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.muted,
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: AppColors.line),
                            ),
                            child: Text(
                              '${product.category} · ${product.audience}',
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: AppColors.inkSoft,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),

                      // Nombre del producto
                      Text(
                        product.name,
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          color: AppColors.ink,
                          letterSpacing: -0.4,
                        ),
                      ),
                      const SizedBox(height: 8),

                      // Precio
                      Text(
                        product.price != null
                            ? currency.format(product.price)
                            : 'Precio por definir',
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                          color: product.price != null
                              ? AppColors.cobaltDark
                              : AppColors.inkSoft,
                          letterSpacing: -0.5,
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Descripción
                      if (product.description != null &&
                          product.description!.trim().isNotEmpty) ...[
                        Text(
                          product.description!,
                          style: TextStyle(
                            color: Colors.grey.shade800,
                            fontSize: 14,
                            height: 1.4,
                          ),
                        ),
                        const SizedBox(height: 20),
                      ],

                      const Divider(),
                      const SizedBox(height: 16),

                      Text(
                        'Sucursal',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      DropdownButtonFormField<int?>(
                        initialValue: _selectedBranchId,
                        decoration: const InputDecoration(
                          hintText: 'Selecciona una sucursal',
                          prefixIcon: Icon(Icons.storefront_outlined),
                        ),
                        items: [
                          const DropdownMenuItem<int?>(
                            value: null,
                            child: Text('Selecciona una sucursal'),
                          ),
                          ...branches.map(
                            (branch) => DropdownMenuItem<int?>(
                              value: branch.id,
                              child: Text(branch.name),
                            ),
                          ),
                        ],
                        onChanged: _changeBranch,
                      ),
                      const SizedBox(height: 20),

                      // Primero se elige el color; la galería y las tallas se adaptan.
                      if (product.colors.isNotEmpty) ...[
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Color',
                              style: Theme.of(context).textTheme.titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            if (_selectedColor != null)
                              TextButton(
                                onPressed: () {
                                  HapticFeedback.selectionClick();
                                  setState(() {
                                    _selectedColor = null;
                                    _selectedImageIndex = 0;
                                  });
                                },
                                style: TextButton.styleFrom(
                                  visualDensity: VisualDensity.compact,
                                ),
                                child: const Text('Quitar selección'),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: product.colors.map((c) {
                            final isSelected = _selectedColor == c;
                            String? colorHex;
                            for (final variant in variants) {
                              if (variant.color == c && variant.hex != null) {
                                colorHex = variant.hex;
                                break;
                              }
                            }
                            final dotColor = _colorFromHex(colorHex);
                            return Tooltip(
                              message: c,
                              child: Semantics(
                                button: true,
                                selected: isSelected,
                                label: 'Color $c',
                                child: InkWell(
                                  customBorder: const CircleBorder(),
                                  onTap: () {
                                    HapticFeedback.selectionClick();
                                    setState(() {
                                      _selectedColor = c;
                                      if (_selectedSize != null &&
                                          !variants.any(
                                            (item) =>
                                                item.active &&
                                                item.color == c &&
                                                item.size == _selectedSize,
                                          )) {
                                        _selectedSize = null;
                                      }
                                      _selectedImageIndex = 0;
                                    });
                                    if (_imagePageController.hasClients) {
                                      _imagePageController.jumpToPage(0);
                                    }
                                  },
                                  child: AnimatedContainer(
                                    duration: const Duration(milliseconds: 160),
                                    width: 42,
                                    height: 42,
                                    padding: const EdgeInsets.all(5),
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      border: Border.all(
                                        color: isSelected
                                            ? AppColors.ink
                                            : Colors.transparent,
                                        width: 1.5,
                                      ),
                                    ),
                                    child: DecoratedBox(
                                      decoration: BoxDecoration(
                                        color: dotColor,
                                        shape: BoxShape.circle,
                                        border: Border.all(color: AppColors.line),
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                        if (_selectedColor != null) ...[
                          const SizedBox(height: 6),
                          Text(
                            _selectedColor!,
                            style: const TextStyle(
                              color: AppColors.inkSoft,
                              fontSize: 12,
                            ),
                          ),
                        ],
                        const SizedBox(height: 20),
                      ],

                      // Solo se muestran las tallas existentes para el color elegido.
                      if (visibleSizes.isNotEmpty) ...[
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Talla',
                              style: Theme.of(context).textTheme.titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            if (_selectedSize != null)
                              TextButton(
                                onPressed: () {
                                  HapticFeedback.selectionClick();
                                  setState(() => _selectedSize = null);
                                },
                                style: TextButton.styleFrom(
                                  visualDensity: VisualDensity.compact,
                                ),
                                child: const Text('Quitar selección'),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: visibleSizes.map((s) {
                            final isSelected = _selectedSize == s;
                            return ChoiceChip(
                              label: Text(s),
                              selected: isSelected,
                              onSelected: (val) {
                                HapticFeedback.selectionClick();
                                setState(() {
                                  _selectedSize = val ? s : null;
                                });
                              },
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 20),
                      ],

                      // Banner de compatibilidad con vestidor virtual (AR)
                      if (product.fittingEnabled) ...[
                        _buildFittingBanner(
                          context,
                          product,
                          measurements,
                          matchedVariant,
                          images,
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Disponibilidad Real en Stock
                      _buildStockAvailabilityCard(matchedVariant),
                      const SizedBox(height: 16),
                    ],
                  ),
                ),
              ],
            ),
          ),
          bottomNavigationBar: _buildBottomActions(
            product,
            matchedVariant,
            branches,
          ),
        );
      },
    );
  }

  void _changeBranch(int? branchId) {
    if (branchId == _selectedBranchId) return;
    HapticFeedback.selectionClick();
    setState(() {
      _selectedBranchId = branchId;
      _selectedSize = null;
      _selectedColor = null;
      _loadData();
    });
  }

  Widget _buildFittingBanner(
    BuildContext context,
    Product product,
    List<ProductMeasurement> measurements,
    ProductVariant? matchedVariant,
    List<ProductImage> images,
  ) {
    return InkWell(
      onTap: () async {
        if (!await _ensureAuthenticated('usar el vestidor virtual con IA')) return;
        if (!context.mounted) return;
        HapticFeedback.mediumImpact();
        context.push(
          '/vestidor',
          extra: {
            'product': product,
            'measurements': measurements,
            'initialVariant': matchedVariant,
            'images': images,
          },
        );
      },
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF0F172A), AppColors.cobalt],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: AppColors.cobalt.withValues(alpha: 0.25),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.auto_awesome,
                color: Colors.white,
                size: 22,
              ),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        'Vestidor Virtual con IA',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                          fontSize: 13,
                          letterSpacing: 0.2,
                        ),
                      ),
                      SizedBox(width: 6),
                      Icon(Icons.bolt_rounded, color: Color(0xFF38BDF8), size: 14),
                    ],
                  ),
                  SizedBox(height: 2),
                  Text(
                    'Descubre tu talla ideal y pruébate el look fotorrealista.',
                    style: TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 11.5,
                    ),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Probar',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                  SizedBox(width: 4),
                  Icon(
                    Icons.arrow_forward_ios_rounded,
                    color: Colors.white,
                    size: 11,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImageGallery(List<ProductImage> images) {
    if (images.isEmpty) {
      return const AspectRatio(
        aspectRatio: 1.05,
        child: AdaptiveImage(
          imageUrl: null,
          aspectRatio: 1.05,
        ),
      );
    }

    return Column(
      children: [
        AspectRatio(
          aspectRatio: 1.05,
          child: PageView.builder(
            controller: _imagePageController,
            itemCount: images.length,
            onPageChanged: (index) =>
                setState(() => _selectedImageIndex = index),
            itemBuilder: (context, index) {
              final img = images[index];
              return AdaptiveImage(
                imageUrl: img.url,
                aspectRatio: 1.05,
                heroTag: index == 0 ? 'product-image-${widget.productId}' : null,
              );
            },
          ),
        ),
        if (images.length > 1) ...[
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(images.length, (index) {
              final isCurrent = index == _selectedImageIndex;
              return AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                margin: const EdgeInsets.symmetric(horizontal: 4),
                width: isCurrent ? 20 : 6,
                height: 6,
                decoration: BoxDecoration(
                  color: isCurrent
                      ? AppColors.cobalt
                      : Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(3),
                ),
              );
            }),
          ),
        ],
      ],
    );
  }

  List<ProductImage> _imagesForSelectedColor(
    List<ProductImage> images,
    List<ProductVariant> variants,
  ) {
    if (_selectedColor == null) return images;
    int? colorId;
    for (final variant in variants) {
      if (variant.color == _selectedColor) {
        colorId = variant.colorId;
        break;
      }
    }
    if (colorId == null) return images;
    final matching = images.where((image) => image.colorId == colorId).toList();
    if (matching.isNotEmpty) return matching;
    return images.where((image) => image.colorId == null).toList();
  }

  Color _colorFromHex(String? value) {
    final normalized = value?.replaceAll('#', '').trim();
    if (normalized == null ||
        !RegExp(r'^[0-9a-fA-F]{6}$').hasMatch(normalized)) {
      return AppColors.muted;
    }
    return Color(int.parse('FF$normalized', radix: 16));
  }

  Widget _buildStockAvailabilityCard(ProductVariant? variant) {
    if (_selectedBranchId == null) {
      return _stockMessage(
        icon: Icons.storefront_outlined,
        message: 'Selecciona una sucursal para consultar la disponibilidad real.',
      );
    }
    if (_selectedSize == null && _selectedColor == null) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.line),
        ),
        child: const Row(
          children: [
            Icon(
              Icons.info_outline_rounded,
              color: AppColors.cobalt,
              size: 20,
            ),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Selecciona una talla o color para consultar disponibilidad en existencias.',
                style: TextStyle(color: AppColors.inkSoft, fontSize: 13),
              ),
            ),
          ],
        ),
      );
    }

    if (variant == null) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.line),
        ),
        child: const Row(
          children: [
            Icon(
              Icons.search_off_rounded,
              color: AppColors.inkSoft,
              size: 20,
            ),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'No hay una variante activa registrada con esa combinación de talla y color.',
                style: TextStyle(color: AppColors.inkSoft, fontSize: 13),
              ),
            ),
          ],
        ),
      );
    }

    if (variant.stock == null) {
      final offline = ref.watch(
        connectivityControllerProvider.select((s) => s.checked && !s.online),
      );
      return _stockMessage(
        icon: offline ? Icons.cloud_off_rounded : Icons.info_outline_rounded,
        message: offline
            ? 'Sin conexión: el stock por sucursal se consulta con internet.'
            : 'La disponibilidad no está informada para esta sucursal.',
      );
    }

    final stock = variant.stock!;
    final hasStock = stock > 0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: hasStock ? const Color(0xFF10B981) : AppColors.line,
          width: hasStock ? 1.5 : 1,
        ),
      ),
      child: Row(
        children: [
          Icon(
            hasStock ? Icons.check_circle_rounded : Icons.cancel_outlined,
            color: hasStock ? const Color(0xFF10B981) : const Color(0xFFEF4444),
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              hasStock
                  ? 'Disponible: $stock unidades'
                  : 'Agotado actualmente',
              style: TextStyle(
                color: hasStock ? AppColors.ink : const Color(0xFFEF4444),
                fontWeight: FontWeight.w800,
                fontSize: 13.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _stockMessage({required IconData icon, required String message}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.cobalt, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: AppColors.inkSoft, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }


  Widget _buildBottomActions(
    Product product,
    ProductVariant? matchedVariant,
    List<BranchItem> branches,
  ) {
    final branch = branches.cast<BranchItem?>().firstWhere(
          (b) => b?.id == _selectedBranchId,
          orElse: () => null,
        );

    // El carrito y las reservas viven en el servidor: sin conexión no se
    // pueden usar aunque el catálogo se vea.
    final offline = ref.watch(
      connectivityControllerProvider.select((s) => s.checked && !s.online),
    );
    final user = ref.watch(authControllerProvider.select((s) => s.user));
    final hasBranch = _selectedBranchId != null;
    final hasVariant = matchedVariant != null && !offline;
    final stock = matchedVariant?.stock ?? 0;
    final hasStock = stock > 0;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: const Border(top: BorderSide(color: AppColors.line, width: 1)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, -3),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (offline || (user?.canOpenOffline ?? false))
                _SaleChannelHint(
                  offline: offline,
                  canSellInStore: user?.canOpenOffline ?? false,
                ),
              if (!hasBranch)
                const Padding(
                  padding: EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      Icon(Icons.info_outline_rounded,
                          size: 16, color: AppColors.warning),
                      SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Selecciona una sucursal arriba para ver stock, reservar o comprar.',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppColors.inkSoft,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              Row(
                children: [
                  // Stepper de Cantidad
                  Container(
                    height: 44,
                    decoration: BoxDecoration(
                      color: AppColors.canvas,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.line),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 36, minHeight: 44),
                          icon: const Icon(Icons.remove, size: 18),
                          onPressed: _quantity > 1 && hasStock
                              ? () {
                                  HapticFeedback.selectionClick();
                                  setState(() => _quantity--);
                                }
                              : null,
                        ),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 4),
                          child: Text(
                            '$_quantity',
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                              color: AppColors.ink,
                            ),
                          ),
                        ),
                        IconButton(
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 36, minHeight: 44),
                          icon: const Icon(Icons.add, size: 18),
                          onPressed: _quantity < stock && hasStock
                              ? () {
                                  HapticFeedback.selectionClick();
                                  setState(() => _quantity++);
                                }
                              : null,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),

                  // Botón Reservar
                  OutlinedButton(
                    onPressed: hasBranch && hasVariant && hasStock && !_addingToCart
                        ? () async {
                            HapticFeedback.lightImpact();
                            if (!await _ensureAuthenticated('agendar una reserva')) return;
                            if (!context.mounted) return;
                            await ReservationBottomSheet.show(
                              context,
                              product: product,
                              variant: matchedVariant,
                              branchId: _selectedBranchId!,
                              branchName: branch?.name ?? 'Sucursal seleccionada',
                            );
                          }
                        : null,
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                      side: BorderSide(
                        color: hasBranch && hasVariant && hasStock
                            ? AppColors.cobalt
                            : AppColors.line,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.event_seat_outlined, size: 18),
                        SizedBox(width: 4),
                        Text('Reservar', style: TextStyle(fontWeight: FontWeight.w700)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),

                  // Botón Agregar al carrito
                  Expanded(
                    child: FilledButton(
                      onPressed: hasBranch && hasVariant && hasStock && !_addingToCart
                          ? () => _addToCart(matchedVariant, branch?.name ?? 'Sucursal')
                          : null,
                      style: FilledButton.styleFrom(
                        backgroundColor: AppColors.cobalt,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      child: _addingToCart
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text(
                              'Agregar',
                              style: TextStyle(
                                fontWeight: FontWeight.w800,
                                fontSize: 15,
                              ),
                            ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<bool> _ensureAuthenticated(String actionDescription) async {
    final authState = ref.read(authControllerProvider);
    if (authState.isAuthenticated) {
      return true;
    }

    final shouldLogin = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.lock_outline_rounded, color: AppColors.cobalt),
            SizedBox(width: 8),
            Text('Inicia sesión', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          ],
        ),
        content: Text(
          'Para $actionDescription necesitas una cuenta en Capricho Store.\n\n¿Deseas iniciar sesión o registrarte ahora?',
          style: const TextStyle(fontSize: 14, color: AppColors.inkSoft, height: 1.45),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Más tarde'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.of(ctx).pop(true),
            icon: const Icon(Icons.login_rounded, size: 18),
            label: const Text('Iniciar sesión'),
            style: FilledButton.styleFrom(backgroundColor: AppColors.cobalt),
          ),
        ],
      ),
    );

    if (shouldLogin == true && mounted) {
      context.push('/login');
    }
    return false;
  }

  Future<void> _addToCart(ProductVariant variant, String branchName) async {
    if (!await _ensureAuthenticated('agregar prendas a tu carrito')) return;
    if (!mounted) return;

    final currentCart = ref.read(cartProvider).value;

    // Regla central: 1 Carrito = 1 Sucursal
    if (currentCart != null &&
        currentCart.idSucursal != null &&
        currentCart.idSucursal != _selectedBranchId &&
        currentCart.items.isNotEmpty) {
      final confirm = await AdaptiveDialogs.showConfirmation(
        context: context,
        title: 'Cambio de sucursal',
        message:
            'Tu carrito actual tiene prendas de ${currentCart.sucursal ?? "otra sucursal"}.\n\nPara respetar la regla comercial "1 Carrito = 1 Sucursal", ¿deseas vaciar el carrito actual y comenzar a comprar en $branchName?',
        confirmText: 'Vaciar e iniciar',
        cancelText: 'Cancelar',
        isDestructive: true,
      );

      if (confirm != true) return;

      setState(() => _addingToCart = true);
      try {
        await ref.read(cartProvider.notifier).clear();
      } catch (_) {}
    }

    setState(() => _addingToCart = true);
    HapticFeedback.mediumImpact();

    try {
      await ref.read(cartProvider.notifier).addItem(
            variantId: variant.id,
            quantity: _quantity,
            branchId: _selectedBranchId,
          );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('¡Agregado al carrito ($branchName)!'),
            backgroundColor: AppColors.cobalt,
            behavior: SnackBarBehavior.floating,
            action: SnackBarAction(
              label: 'Ver carrito',
              textColor: Colors.white,
              onPressed: () => context.go('/carrito'),
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceAll('ApiException: ', '')),
            backgroundColor: AppColors.danger,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _addingToCart = false);
      }
    }
  }
}

class _ProductDetailData {
  const _ProductDetailData({
    required this.product,
    required this.images,
    required this.variants,
    required this.measurements,
    required this.branches,
  });

  final Product product;
  final List<ProductImage> images;
  final List<ProductVariant> variants;
  final List<ProductMeasurement> measurements;
  final List<BranchItem> branches;
}

/// Explica por qué no se puede comprar aquí y dónde vender: sin conexión el
/// carrito no funciona, y el carrito es de clientes (un trabajador vende en
/// Panel → Offline, que funciona con o sin internet).
class _SaleChannelHint extends StatelessWidget {
  const _SaleChannelHint({required this.offline, required this.canSellInStore});

  final bool offline;
  final bool canSellInStore;

  @override
  Widget build(BuildContext context) {
    final message = offline
        ? 'Sin conexión: agregar al carrito y reservar necesitan internet.'
              '${canSellInStore ? ' Para vender en tienda usa Panel → Offline.' : ''}'
        : 'El carrito es para compras de clientes. Para registrar una venta '
              'en tienda usa Panel → Offline.';
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(
            offline ? Icons.cloud_off_rounded : Icons.point_of_sale_outlined,
            size: 16,
            color: offline ? AppColors.warning : AppColors.cobalt,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.inkSoft,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          if (canSellInStore)
            TextButton(
              onPressed: () => context.go('/admin/offline'),
              child: const Text('Ir a vender'),
            ),
        ],
      ),
    );
  }
}
