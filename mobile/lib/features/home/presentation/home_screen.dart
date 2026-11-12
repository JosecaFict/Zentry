import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/catalog/data/catalog_repository.dart';
import 'package:capricho_store/features/catalog/data/catalog_source.dart';
import 'package:capricho_store/features/catalog/domain/catalog_models.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_image.dart';
import 'package:capricho_store/shared/widgets/brand_wordmark.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  late Future<List<CategoryItem>> _categoriesFuture;
  late Future<ProductPage> _featuredProductsFuture;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  void _loadData() {
    final repo = ref.read(catalogRepositoryProvider);
    _categoriesFuture = repo.categories();
    _featuredProductsFuture = repo.products(
      const CatalogQuery(sort: '-created_at', pageSize: 6),
    );
  }

  Future<void> _refresh() async {
    setState(() {
      _loadData();
    });
    await Future.wait([_categoriesFuture, _featuredProductsFuture]);
  }

  @override
  Widget build(BuildContext context) {
    refreshCatalogOnReconnect(ref, () => setState(_loadData));
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
                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                  backgroundColor: AppColors.cobalt,
                  child: const Icon(Icons.notifications_outlined),
                ),
                onPressed: () => context.push('/notificaciones'),
              );
            },
          ),
          IconButton(
            tooltip: 'Buscar en catálogo',
            icon: const Icon(Icons.search_rounded),
            onPressed: () => context.go('/catalogo'),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(color: AppColors.line, height: 1),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        color: AppColors.cobalt,
        child: ListView(
          padding: const EdgeInsets.only(bottom: 40),
          children: [
            // 1. Hero Editorial
            _buildHeroBanner(context),
            const SizedBox(height: 32),

            // 2. Explorar por público
            _buildAudienceSection(context),
            const SizedBox(height: 36),

            // 3. El catálogo, sin categorías inventadas
            _buildCategoriesSection(context),
            const SizedBox(height: 36),

            // 4. Prendas recientes
            _buildFeaturedSection(context, currency),
          ],
        ),
      ),
    );
  }

  // --- 1. HERO BANNER EDITORIAL ---
  Widget _buildHeroBanner(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.line),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Stack(
            children: [
              AspectRatio(
                aspectRatio: 16 / 10,
                child: Image.asset(
                  'assets/images/hero-catalogo-oficial.jpg',
                  fit: BoxFit.cover,
                  alignment: const Alignment(0, -0.25),
                ),
              ),
              Positioned(
                bottom: 8,
                right: 8,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xD0121418),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'FOTOGRAFÍA DE REFERENCIA',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 8.5,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.8,
                    ),
                  ),
                ),
              ),
            ],
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Vestir también es elegir',
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                    letterSpacing: -0.8,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Encuentra prendas reales por estilo, talla y color.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppColors.inkSoft,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: () => context.go('/catalogo'),
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.cobalt,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    child: const Text(
                      'Ver catálogo',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // --- 2. ACCESOS POR PÚBLICO OBJETIVO ---
  Widget _buildAudienceSection(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'FOTOGRAFÍAS DE REFERENCIA DEL CATÁLOGO OFICIAL',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.1,
              color: AppColors.inkSoft,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _AudienceTile(
                  imagePath: 'assets/images/acceso-hombre-polo.jpg',
                  title: 'Hombre',
                  subtitle: 'Poleras · Camisas · Polos',
                  onTap: () => context.go(
                    Uri(
                      path: '/catalogo',
                      queryParameters: {'publico': 'HOMBRE'},
                    ).toString(),
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: _AudienceTile(
                  imagePath: 'assets/images/acceso-mujer-blusa.jpg',
                  title: 'Mujer',
                  subtitle: 'Poleras · Camisas · Blusas',
                  onTap: () => context.go(
                    Uri(
                      path: '/catalogo',
                      queryParameters: {'publico': 'MUJER'},
                    ).toString(),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // --- 3. CATEGORÍAS OFICIALES ---
  Widget _buildCategoriesSection(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'El catálogo, sin categorías inventadas',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w800,
              color: AppColors.ink,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Cuatro tipos de prenda. Dos públicos. Una selección clara.',
            style: TextStyle(
              color: AppColors.inkSoft,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 16),
          FutureBuilder<List<CategoryItem>>(
            future: _categoriesFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const SizedBox(
                  height: 70,
                  child: Center(
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                );
              }

              if (snapshot.hasError) {
                return Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.line),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.cloud_off_rounded, color: AppColors.danger, size: 20),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'No pudimos cargar las categorías.',
                          style: TextStyle(fontSize: 12),
                        ),
                      ),
                      TextButton(
                        onPressed: () => setState(() => _loadData()),
                        child: const Text('Reintentar'),
                      ),
                    ],
                  ),
                );
              }

              final categories = snapshot.data ?? [];
              if (categories.isEmpty) {
                return const Text('No hay categorías disponibles.');
              }

              return Wrap(
                spacing: 8,
                runSpacing: 8,
                children: categories.map((cat) {
                  return InkWell(
                    onTap: () => context.go(
                      Uri(
                        path: '/catalogo',
                        queryParameters: {'categoria': cat.name},
                      ).toString(),
                    ),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.line),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            _getCategoryIcon(cat.name),
                            size: 16,
                            color: AppColors.cobalt,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            cat.name,
                            style: const TextStyle(
                              color: AppColors.ink,
                              fontWeight: FontWeight.w700,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              );
            },
          ),
          const SizedBox(height: 18),
          // Strip visual editorial
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.line),
            ),
            clipBehavior: Clip.antiAlias,
            child: Stack(
              children: [
                AspectRatio(
                  aspectRatio: 16 / 7,
                  child: Image.asset(
                    'assets/images/catalogo-prendas-oficiales.jpg',
                    fit: BoxFit.cover,
                  ),
                ),
                Positioned(
                  bottom: 6,
                  right: 6,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                    decoration: BoxDecoration(
                      color: const Color(0xD0121418),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'COMPOSICIÓN VISUAL DE REFERENCIA',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 8,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.6,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // --- 4. PRENDAS RECIENTES ---
  Widget _buildFeaturedSection(BuildContext context, NumberFormat currency) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Prendas recientes',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                        color: AppColors.ink,
                        letterSpacing: -0.5,
                      ),
                    ),
                    const SizedBox(height: 2),
                    const Text(
                      'Datos obtenidos directamente del catálogo.',
                      style: TextStyle(
                        color: AppColors.inkSoft,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              InkWell(
                onTap: () => context.go('/catalogo'),
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 4),
                  child: Text(
                    'Ver catálogo',
                    style: TextStyle(
                      color: AppColors.cobaltDark,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          FutureBuilder<ProductPage>(
            future: _featuredProductsFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const SizedBox(
                  height: 120,
                  child: Center(
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                );
              }

              if (snapshot.hasError) {
                return Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.line),
                  ),
                  child: Column(
                    children: [
                      const Text(
                        'El catálogo no respondió',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: AppColors.ink,
                        ),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'No pudimos cargar los productos recientes.',
                        style: TextStyle(color: AppColors.inkSoft, fontSize: 12),
                      ),
                      const SizedBox(height: 10),
                      OutlinedButton(
                        onPressed: () => setState(() => _loadData()),
                        child: const Text('Reintentar'),
                      ),
                    ],
                  ),
                );
              }

              final products = snapshot.data?.items ?? [];
              if (products.isEmpty) {
                return Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.line),
                  ),
                  child: Column(
                    children: [
                      const Icon(
                        Icons.inventory_2_outlined,
                        size: 40,
                        color: AppColors.inkSoft,
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Aún no hay productos publicados',
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          color: AppColors.ink,
                          fontSize: 15,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        'Cuando el catálogo tenga productos activos, aparecerán aquí.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: AppColors.inkSoft, fontSize: 13),
                      ),
                      const SizedBox(height: 16),
                      OutlinedButton(
                        onPressed: () => context.go('/catalogo'),
                        child: const Text('Explorar todo el catálogo'),
                      ),
                    ],
                  ),
                );
              }

              return GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 14,
                  mainAxisSpacing: 16,
                  childAspectRatio: 0.65,
                ),
                itemCount: products.length,
                itemBuilder: (context, index) {
                  final product = products[index];
                  return _ProductCard(product: product, currency: currency);
                },
              );
            },
          ),
        ],
      ),
    );
  }

  IconData _getCategoryIcon(String name) {
    final lower = name.toLowerCase();
    if (lower.contains('blusa')) return Icons.woman_rounded;
    if (lower.contains('camisa')) return Icons.dry_cleaning_rounded;
    if (lower.contains('polera') || lower.contains('remera')) {
      return Icons.checkroom_rounded;
    }
    if (lower.contains('polo')) return Icons.sports_tennis_rounded;
    return Icons.category_outlined;
  }
}

class _AudienceTile extends StatelessWidget {
  const _AudienceTile({
    required this.imagePath,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final String imagePath;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        height: 200,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.line),
        ),
        clipBehavior: Clip.antiAlias,
        child: Stack(
          fit: StackFit.expand,
          children: [
            Image.asset(
              imagePath,
              fit: BoxFit.cover,
            ),
            Positioned(
              left: 10,
              right: 10,
              bottom: 10,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xE8121418),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.3,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: Color(0xFFC7CBD1),
                        fontSize: 9.5,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({required this.product, required this.currency});
  final Product product;
  final NumberFormat currency;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => context.push('/productos/${product.id}'),
      borderRadius: BorderRadius.circular(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.muted,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.line),
              ),
              clipBehavior: Clip.antiAlias,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  if (product.image?.url != null && product.image!.url.isNotEmpty)
                    // Usa la misma lógica offline que el resto del catálogo.
                    AdaptiveImage(
                      imageUrl: product.image!.url,
                      fit: BoxFit.cover,
                      borderRadius: BorderRadius.zero,
                    )
                  else
                    Container(
                      color: AppColors.muted,
                      child: const Icon(
                        Icons.checkroom_rounded,
                        size: 36,
                        color: AppColors.inkSoft,
                      ),
                    ),
                  Positioned(
                    top: 8,
                    left: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xD0121418),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        product.audience,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 8.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 8, left: 2, right: 2),
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
                const SizedBox(height: 2),
                Text(
                  product.price != null
                      ? currency.format(product.price)
                      : 'Precio por definir',
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: product.price != null ? AppColors.cobaltDark : AppColors.inkSoft,
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
