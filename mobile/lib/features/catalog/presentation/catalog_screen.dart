import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/catalog/data/catalog_repository.dart';
import 'package:capricho_store/features/catalog/data/catalog_source.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_card_pressable.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_image.dart';
import 'package:capricho_store/shared/widgets/brand_wordmark.dart';
import 'package:capricho_store/shared/widgets/message_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

class CatalogScreen extends ConsumerStatefulWidget {
  const CatalogScreen({super.key});

  @override
  ConsumerState<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends ConsumerState<CatalogScreen> {
  CatalogQuery query = const CatalogQuery();
  late Future<ProductPage> request;

  List<CategoryItem> _availableCategories = [];
  List<BrandItem> _availableBrands = [];
  List<SizeItem> _availableSizes = [];
  List<ColorItem> _availableColors = [];
  List<SeasonItem> _availableSeasons = [];
  List<BranchItem> _availableBranches = [];

  @override
  void initState() {
    super.initState();
    final user = ref.read(authControllerProvider).user;
    if (user != null && user.isBranchLocked) {
      query = CatalogQuery(branchId: user.idSucursal);
    }
    _loadMetadata();
    request = _load();
  }

  Future<void> _loadMetadata() async {
    final repo = ref.read(catalogRepositoryProvider);
    try {
      final results = await Future.wait([
        repo.categories(),
        repo.brands(),
        repo.sizes(),
        repo.colors(),
        repo.seasons(),
        repo.branches(),
      ]);
      if (mounted) {
        setState(() {
          _availableCategories = results[0] as List<CategoryItem>;
          _availableBrands = results[1] as List<BrandItem>;
          _availableSizes = results[2] as List<SizeItem>;
          _availableColors = results[3] as List<ColorItem>;
          _availableSeasons = results[4] as List<SeasonItem>;
          _availableBranches = results[5] as List<BranchItem>;
        });
      }
    } catch (_) {
      // Ignorar fallo de metadatos si no hay conexión, se reintentará en el refresh
    }
  }

  Future<ProductPage> _load() =>
      ref.read(catalogRepositoryProvider).products(query);

  void _setQuery(CatalogQuery next) {
    setState(() {
      query = next;
      request = _load();
    });
  }

  Future<void> _refresh() async {
    _loadMetadata();
    _setQuery(query);
    await request;
  }

  Future<void> _openFiltersSheet() async {
    final user = ref.read(authControllerProvider).user;
    final isLocked = user != null && user.isBranchLocked;
    var tempCategory = query.category;
    var tempAudience = query.audience;
    var tempBrand = query.brand;
    var tempSize = query.size;
    var tempColor = query.color;
    var tempSeason = query.season;
    var tempBranchId = isLocked ? user.idSucursal : query.branchId;
    var tempFittingEnabled = query.fittingEnabled;

    final result = await showModalBottomSheet<CatalogQuery>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => DraggableScrollableSheet(
          initialChildSize: 0.78,
          minChildSize: 0.5,
          maxChildSize: 0.94,
          expand: false,
          builder: (context, scrollController) => SafeArea(
            child: ListView(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Filtrar Catálogo',
                      style: Theme.of(context).textTheme.titleLarge
                          ?.copyWith(fontWeight: FontWeight.bold),
                    ),
                    TextButton(
                      onPressed: () {
                        HapticFeedback.selectionClick();
                        setSheetState(() {
                          tempCategory = null;
                          tempAudience = null;
                          tempBrand = null;
                          tempSize = null;
                          tempColor = null;
                          tempSeason = null;
                          tempBranchId = isLocked ? user?.idSucursal : null;
                          tempFittingEnabled = null;
                        });
                      },
                      child: const Text('Limpiar todo'),
                    ),
                  ],
                ),
                const Divider(),
                const SizedBox(height: 10),

                // Público Objetivo
                _buildFilterLabel('Público Objetivo'),
                SegmentedButton<String?>(
                  segments: const [
                    ButtonSegment(value: null, label: Text('Todos')),
                    ButtonSegment(value: 'MUJER', label: Text('Mujer')),
                    ButtonSegment(value: 'HOMBRE', label: Text('Hombre')),
                  ],
                  selected: {tempAudience},
                  onSelectionChanged: (values) {
                    HapticFeedback.selectionClick();
                    setSheetState(() => tempAudience = values.first);
                  },
                ),
                const SizedBox(height: 18),

                // Categoría
                _buildFilterLabel('Categoría'),
                DropdownButtonFormField<String?>(
                  initialValue: tempCategory,
                  decoration: const InputDecoration(
                    hintText: 'Todas las categorías',
                    prefixIcon: Icon(Icons.category_outlined),
                  ),
                  items: [
                    const DropdownMenuItem(value: null, child: Text('Todas')),
                    ..._availableCategories.map(
                      (c) =>
                          DropdownMenuItem(value: c.name, child: Text(c.name)),
                    ),
                  ],
                  onChanged: (val) {
                    HapticFeedback.selectionClick();
                    setSheetState(() => tempCategory = val);
                  },
                ),
                const SizedBox(height: 18),

                // Sucursal (Filtro por tienda física)
                if (_availableBranches.isNotEmpty) ...[
                  _buildFilterLabel('Sucursal'),
                  if (isLocked)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 12,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.canvas,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.line),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.lock_outline_rounded,
                            size: 18,
                            color: AppColors.inkSoft,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              user?.assignedBranchLabel ??
                                  'Sucursal asignada',
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 14,
                                color: AppColors.ink,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.cobalt.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'Asignada',
                              style: TextStyle(
                                fontSize: 10.5,
                                fontWeight: FontWeight.w700,
                                color: AppColors.cobalt,
                              ),
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    DropdownButtonFormField<int?>(
                      initialValue: tempBranchId,
                      decoration: const InputDecoration(
                        hintText: 'Todas las sucursales',
                        prefixIcon: Icon(Icons.storefront_outlined),
                      ),
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text('Todas las sucursales'),
                        ),
                        ..._availableBranches.map(
                          (b) => DropdownMenuItem(
                            value: b.id,
                            child: Text(
                              b.address.isNotEmpty
                                  ? '${b.name} (${b.address})'
                                  : b.name,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ],
                      onChanged: (val) {
                        HapticFeedback.selectionClick();
                        setSheetState(() => tempBranchId = val);
                      },
                    ),
                  const SizedBox(height: 18),
                ],

                // Marca (si existen marcas registradas)
                if (_availableBrands.isNotEmpty) ...[
                  _buildFilterLabel('Marca'),
                  DropdownButtonFormField<String?>(
                    initialValue: tempBrand,
                    decoration: const InputDecoration(
                      hintText: 'Todas las marcas',
                      prefixIcon: Icon(Icons.branding_watermark_outlined),
                    ),
                    items: [
                      const DropdownMenuItem(value: null, child: Text('Todas')),
                      ..._availableBrands.map(
                        (b) => DropdownMenuItem(
                          value: b.name,
                          child: Text(b.name),
                        ),
                      ),
                    ],
                    onChanged: (val) {
                      HapticFeedback.selectionClick();
                      setSheetState(() => tempBrand = val);
                    },
                  ),
                  const SizedBox(height: 18),
                ],

                // Tallas
                if (_availableSizes.isNotEmpty) ...[
                  _buildFilterLabel('Talla'),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      ChoiceChip(
                        label: const Text('Todas'),
                        selected: tempSize == null,
                        onSelected: (selected) {
                          if (selected) {
                            HapticFeedback.selectionClick();
                            setSheetState(() => tempSize = null);
                          }
                        },
                      ),
                      ..._availableSizes.map((s) {
                        final isSelected = tempSize == s.name;
                        return ChoiceChip(
                          label: Text(s.name),
                          selected: isSelected,
                          onSelected: (selected) {
                            HapticFeedback.selectionClick();
                            setSheetState(
                              () => tempSize = selected ? s.name : null,
                            );
                          },
                        );
                      }),
                    ],
                  ),
                  const SizedBox(height: 18),
                ],

                // Colores
                if (_availableColors.isNotEmpty) ...[
                  _buildFilterLabel('Color'),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      ChoiceChip(
                        label: const Text('Todos'),
                        selected: tempColor == null,
                        onSelected: (selected) {
                          if (selected) {
                            HapticFeedback.selectionClick();
                            setSheetState(() => tempColor = null);
                          }
                        },
                      ),
                      ..._availableColors.map((c) {
                        final isSelected = tempColor == c.name;
                        Color? dotColor;
                        if (c.hex != null) {
                          final hexClean = c.hex!.replaceAll('#', '');
                          if (hexClean.length == 6) {
                            dotColor = Color(int.parse('0xFF$hexClean'));
                          }
                        }
                        return ChoiceChip(
                          avatar: dotColor != null
                              ? CircleAvatar(
                                  backgroundColor: dotColor,
                                  radius: 6,
                                )
                              : null,
                          label: Text(c.name),
                          selected: isSelected,
                          onSelected: (selected) {
                            HapticFeedback.selectionClick();
                            setSheetState(
                              () => tempColor = selected ? c.name : null,
                            );
                          },
                        );
                      }),
                    ],
                  ),
                  const SizedBox(height: 18),
                ],

                // Temporada
                if (_availableSeasons.isNotEmpty) ...[
                  _buildFilterLabel('Temporada'),
                  DropdownButtonFormField<String?>(
                    initialValue: tempSeason,
                    decoration: const InputDecoration(
                      hintText: 'Todas las temporadas',
                      prefixIcon: Icon(Icons.wb_sunny_outlined),
                    ),
                    items: [
                      const DropdownMenuItem(value: null, child: Text('Todas')),
                      ..._availableSeasons.map(
                        (s) => DropdownMenuItem(
                          value: s.name,
                          child: Text(s.name),
                        ),
                      ),
                    ],
                    onChanged: (val) {
                      HapticFeedback.selectionClick();
                      setSheetState(() => tempSeason = val);
                    },
                  ),
                  const SizedBox(height: 18),
                ],

                // Vestidor Virtual (Compatibilidad con realidad aumentada)
                _buildFilterLabel('Vestidor Virtual'),
                Container(
                  decoration: BoxDecoration(
                    color: AppColors.muted,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.line),
                  ),
                  child: SwitchListTile.adaptive(
                    value: tempFittingEnabled ?? false,
                    title: const Text(
                      'Solo con vestidor virtual',
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    subtitle: const Text(
                      'Prendas compatibles con probador virtual',
                      style: TextStyle(
                        fontSize: 11.5,
                        color: AppColors.inkSoft,
                      ),
                    ),
                    secondary: const Icon(
                      Icons.auto_awesome,
                      color: AppColors.cobalt,
                    ),
                    activeThumbColor: AppColors.cobalt,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 2,
                    ),
                    onChanged: (val) {
                      HapticFeedback.selectionClick();
                      setSheetState(
                        () => tempFittingEnabled = val ? true : null,
                      );
                    },
                  ),
                ),
                const SizedBox(height: 20),

                FilledButton(
                  onPressed: () {
                    HapticFeedback.lightImpact();
                    Navigator.pop(
                      sheetContext,
                      query.copyWith(
                        category: tempCategory,
                        clearCategory: tempCategory == null,
                        audience: tempAudience,
                        clearAudience: tempAudience == null,
                        brand: tempBrand,
                        clearBrand: tempBrand == null,
                        size: tempSize,
                        clearSize: tempSize == null,
                        color: tempColor,
                        clearColor: tempColor == null,
                        season: tempSeason,
                        clearSeason: tempSeason == null,
                        branchId: tempBranchId,
                        clearBranch: tempBranchId == null,
                        fittingEnabled: tempFittingEnabled,
                        clearFittingEnabled: tempFittingEnabled == null,
                        page: 1, // Reiniciar a página 1 tras filtrar
                      ),
                    );
                  },
                  child: const Text('Aplicar Filtros'),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    if (result != null) {
      _setQuery(result);
    }
  }

  Widget _buildFilterLabel(String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        label,
        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    refreshCatalogOnReconnect(ref, () {
      _loadMetadata();
      _setQuery(query);
    });
    final currency = NumberFormat.currency(locale: 'es_BO', symbol: 'Bs.');

    return Scaffold(
      appBar: AppBar(
        title: const BrandWordmark(compact: true),
        centerTitle: false,
        actions: [
          Consumer(
            builder: (context, ref, _) {
              final unreadCount = ref.watch(unreadNotificationsCountProvider);
              return IconButton(
                tooltip: 'Notificaciones',
                icon: Badge(
                  isLabelVisible: unreadCount > 0,
                  label: Text(
                    unreadCount > 99 ? '99+' : '$unreadCount',
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  backgroundColor: AppColors.cobalt,
                  child: const Icon(Icons.notifications_outlined),
                ),
                onPressed: () => context.push('/notificaciones'),
              );
            },
          ),
          IconButton(
            tooltip: 'Filtros',
            icon: Badge(
              isLabelVisible: query.hasActiveFilters,
              child: const Icon(Icons.tune_rounded),
            ),
            onPressed: _openFiltersSheet,
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(color: AppColors.line, height: 1),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              sliver: SliverList.list(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _openFiltersSheet,
                          icon: Badge(
                            isLabelVisible: query.hasActiveFilters,
                            child: const Icon(Icons.tune_rounded, size: 18),
                          ),
                          label: Text(
                            query.hasActiveFilters
                                ? 'Filtros activos'
                                : 'Todos los filtros',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          isExpanded: true,
                          initialValue: query.sort,
                          decoration: const InputDecoration(
                            prefixIcon: Icon(Icons.swap_vert_rounded, size: 18),
                            prefixIconConstraints: BoxConstraints(minWidth: 30),
                            contentPadding: EdgeInsets.symmetric(
                              horizontal: 6,
                            ),
                          ),
                          items: const [
                            DropdownMenuItem(
                              value: 'nombre',
                              child: Text('Nombre A-Z', overflow: TextOverflow.ellipsis),
                            ),
                            DropdownMenuItem(
                              value: '-nombre',
                              child: Text('Nombre Z-A', overflow: TextOverflow.ellipsis),
                            ),
                            DropdownMenuItem(
                              value: 'precio',
                              child: Text('Menor precio', overflow: TextOverflow.ellipsis),
                            ),
                            DropdownMenuItem(
                              value: '-precio',
                              child: Text('Mayor precio', overflow: TextOverflow.ellipsis),
                            ),
                            DropdownMenuItem(
                              value: '-created_at',
                              child: Text('Novedades', overflow: TextOverflow.ellipsis),
                            ),
                          ],
                          onChanged: (val) {
                            if (val != null) {
                              _setQuery(query.copyWith(sort: val, page: 1));
                            }
                          },
                        ),
                      ),
                    ],
                  ),
                  if (query.hasActiveFilters) ...[
                    const SizedBox(height: 10),
                    _buildActiveFilterChips(),
                  ],
                ],
              ),
            ),
            FutureBuilder<ProductPage>(
              future: request,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return SliverPadding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                    sliver: SliverGrid(
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 14,
                            childAspectRatio: 0.64,
                          ),
                      delegate: SliverChildBuilderDelegate(
                        (context, index) => const _CatalogProductShimmerCard(),
                        childCount: 6,
                      ),
                    ),
                  );
                }

                if (snapshot.hasError) {
                  return SliverFillRemaining(
                    child: MessageState(
                      title: 'El catálogo no pudo cargar',
                      message: snapshot.error.toString(),
                      onRetry: _refresh,
                    ),
                  );
                }

                final page = snapshot.data!;
                if (page.items.isEmpty) {
                  return SliverFillRemaining(
                    child: Center(
                      child: Container(
                        margin: const EdgeInsets.all(24),
                        padding: const EdgeInsets.symmetric(
                          vertical: 32,
                          horizontal: 20,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.line),
                        ),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.inventory_2_outlined,
                              size: 44,
                              color: AppColors.inkSoft,
                            ),
                            const SizedBox(height: 14),
                            Text(
                              query.hasActiveFilters
                                  ? 'No hay prendas con estos filtros'
                                  : 'Aún no hay productos publicados',
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                                fontSize: 16,
                                color: AppColors.ink,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: 8),
                            Text(
                              query.hasActiveFilters
                                  ? 'Prueba quitando uno o más filtros para ampliar la búsqueda.'
                                  : 'Cuando el catálogo tenga productos activos, aparecerán aquí.',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: AppColors.inkSoft,
                                fontSize: 13,
                              ),
                            ),
                            const SizedBox(height: 20),
                            if (query.hasActiveFilters)
                              FilledButton(
                                onPressed: () {
                                  _setQuery(const CatalogQuery());
                                },
                                child: const Text('Limpiar filtros'),
                              )
                            else
                              OutlinedButton.icon(
                                onPressed: _refresh,
                                icon: const Icon(
                                  Icons.refresh_rounded,
                                  size: 18,
                                ),
                                label: const Text('Actualizar'),
                              ),
                          ],
                        ),
                      ),
                    ),
                  );
                }

                return SliverPadding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  sliver: SliverGrid(
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          crossAxisSpacing: 12,
                          mainAxisSpacing: 14,
                          childAspectRatio: 0.64,
                        ),
                    delegate: SliverChildBuilderDelegate((context, index) {
                      final product = page.items[index];
                      return _CatalogProductCard(
                        product: product,
                        currency: currency,
                        branchId: query.branchId,
                      );
                    }, childCount: page.items.length),
                  ),
                );
              },
            ),
            // Controles de paginación
            SliverToBoxAdapter(
              child: FutureBuilder<ProductPage>(
                future: request,
                builder: (context, snapshot) {
                  if (!snapshot.hasData) return const SizedBox.shrink();
                  final page = snapshot.data!;
                  if (page.pages <= 1) return const SizedBox.shrink();

                  return Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 14,
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        OutlinedButton.icon(
                          onPressed: query.page > 1
                              ? () => _setQuery(
                                  query.copyWith(page: query.page - 1),
                                )
                              : null,
                          icon: const Icon(Icons.chevron_left_rounded),
                          label: const Text('Anterior'),
                        ),
                        Text(
                          'Página ${page.page} de ${page.pages}',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        OutlinedButton.icon(
                          onPressed: query.page < page.pages
                              ? () => _setQuery(
                                  query.copyWith(page: query.page + 1),
                                )
                              : null,
                          icon: const Icon(Icons.chevron_right_rounded),
                          label: const Text('Siguiente'),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActiveFilterChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          if (query.category != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text('Cat: ${query.category}'),
                onDeleted: () =>
                    _setQuery(query.copyWith(clearCategory: true, page: 1)),
              ),
            ),
          if (query.audience != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text(query.audience == 'MUJER' ? 'Mujer' : 'Hombre'),
                onDeleted: () =>
                    _setQuery(query.copyWith(clearAudience: true, page: 1)),
              ),
            ),
          if (query.brand != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text('Marca: ${query.brand}'),
                onDeleted: () =>
                    _setQuery(query.copyWith(clearBrand: true, page: 1)),
              ),
            ),
          if (query.size != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text('Talla: ${query.size}'),
                onDeleted: () =>
                    _setQuery(query.copyWith(clearSize: true, page: 1)),
              ),
            ),
          if (query.color != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text('Color: ${query.color}'),
                onDeleted: () =>
                    _setQuery(query.copyWith(clearColor: true, page: 1)),
              ),
            ),
          if (query.season != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text('Temp: ${query.season}'),
                onDeleted: () =>
                    _setQuery(query.copyWith(clearSeason: true, page: 1)),
              ),
            ),
          if (query.branchId != null) ...[
            Builder(
              builder: (context) {
                final user = ref.watch(authControllerProvider).user;
                final isLocked = user != null && user.isBranchLocked;
                final match = _availableBranches.cast<BranchItem?>().firstWhere(
                  (b) => b?.id == query.branchId,
                  orElse: () => null,
                );
                final name = match != null
                    ? match.name
                    : 'Sucursal #${query.branchId}';
                return Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: Chip(
                    avatar: Icon(
                      isLocked
                          ? Icons.lock_outline_rounded
                          : Icons.storefront_outlined,
                      size: 16,
                      color: isLocked ? AppColors.cobalt : null,
                    ),
                    label: Text(isLocked ? '$name (Asignada)' : name),
                    onDeleted: isLocked
                        ? null
                        : () => _setQuery(
                            query.copyWith(clearBranch: true, page: 1),
                          ),
                  ),
                );
              },
            ),
          ],
          if (query.fittingEnabled == true)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                avatar: const Icon(
                  Icons.auto_awesome,
                  size: 15,
                  color: AppColors.cobalt,
                ),
                label: const Text('Con Vestidor'),
                onDeleted: () => _setQuery(
                  query.copyWith(clearFittingEnabled: true, page: 1),
                ),
              ),
            ),
          TextButton(
            onPressed: () {
              HapticFeedback.selectionClick();
              _setQuery(const CatalogQuery());
            },
            child: const Text('Borrar todos'),
          ),
        ],
      ),
    );
  }
}

class _CatalogProductCard extends StatelessWidget {
  const _CatalogProductCard({
    required this.product,
    required this.currency,
    this.branchId,
  });
  final Product product;
  final NumberFormat currency;
  final int? branchId;

  @override
  Widget build(BuildContext context) {
    return AdaptiveCardPressable(
      onTap: () => context.push(
        Uri(
          path: '/productos/${product.id}',
          queryParameters: {
            if (branchId != null) 'sucursal': branchId.toString(),
          },
        ).toString(),
      ),
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: AppColors.line, width: 0.8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: Stack(
              fit: StackFit.expand,
              children: [
                AdaptiveImage(
                  imageUrl: product.image?.url,
                  heroTag: 'product-image-${product.id}',
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(15),
                  ),
                ),
                Positioned(
                  top: 8,
                  left: 8,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xD0121418),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      product.audience,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 8.5,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.4,
                      ),
                    ),
                  ),
                ),
                if (product.fittingEnabled)
                  Positioned(
                    top: 8,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.cobalt.withValues(alpha: 0.92),
                        borderRadius: BorderRadius.circular(6),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.cobalt.withValues(alpha: 0.35),
                            blurRadius: 4,
                            offset: const Offset(0, 1.5),
                          ),
                        ],
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.auto_awesome,
                            size: 10,
                            color: Colors.white,
                          ),
                          SizedBox(width: 3),
                          Text(
                            'VESTIDOR',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 8,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  product.brand.toUpperCase(),
                  style: const TextStyle(
                    fontSize: 9.5,
                    fontWeight: FontWeight.w800,
                    color: AppColors.cobalt,
                    letterSpacing: 0.5,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  product.name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    color: AppColors.ink,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (product.sizes.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    'Tallas: ${product.sizes.join(', ')}',
                    style: const TextStyle(
                      fontSize: 10,
                      color: AppColors.inkSoft,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 3),
                Text(
                  product.price != null
                      ? currency.format(product.price)
                      : 'Precio por definir',
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: product.price != null
                        ? AppColors.cobaltDark
                        : AppColors.inkSoft,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CatalogProductShimmerCard extends StatelessWidget {
  const _CatalogProductShimmerCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.line, width: 0.8),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: ShimmerBox(
              borderRadius: BorderRadius.vertical(top: Radius.circular(15)),
            ),
          ),
          Padding(
            padding: EdgeInsets.fromLTRB(10, 10, 10, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ShimmerBox(width: 50, height: 10),
                SizedBox(height: 6),
                ShimmerBox(width: 110, height: 12),
                SizedBox(height: 6),
                ShimmerBox(width: 70, height: 10),
                SizedBox(height: 8),
                ShimmerBox(width: 60, height: 14),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
