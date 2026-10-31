import 'package:capricho_store/app/navigation_memory.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/shared/widgets/brand_wordmark.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

class AdminShell extends ConsumerWidget {
  const AdminShell({required this.location, required this.child, super.key});

  final String location;
  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    if (!auth.initialized) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final user = auth.user;
    if (user == null) return const SizedBox.shrink();

    NavigationMemory.rememberPanel(location);
    final destinations = <_PanelDestination>[
      const _PanelDestination(
        location: '/admin/resumen',
        label: 'Resumen',
        icon: Icons.dashboard_outlined,
        selectedIcon: Icons.dashboard_rounded,
      ),
      if (user.canAccessSection(OperationalSection.inventory))
        const _PanelDestination(
          location: '/admin/inventario',
          label: 'Inventario',
          icon: Icons.inventory_2_outlined,
          selectedIcon: Icons.inventory_2_rounded,
        ),
      if (user.canAccessSection(OperationalSection.operations))
        const _PanelDestination(
          location: '/admin/operaciones',
          label: 'Operaciones',
          icon: Icons.swap_horiz_outlined,
          selectedIcon: Icons.swap_horiz_rounded,
        ),
      if (user.canViewInventory && user.canManageOrders)
        const _PanelDestination(
          location: '/admin/offline',
          label: 'Offline',
          icon: Icons.sync_alt_outlined,
          selectedIcon: Icons.sync_alt_rounded,
        ),
      const _PanelDestination(
        location: '/admin/perfil',
        label: 'Cuenta',
        icon: Icons.person_outline_rounded,
        selectedIcon: Icons.person_rounded,
      ),
    ];

    var selectedIndex = destinations.indexWhere(
      (destination) => location.startsWith(destination.location),
    );
    if (selectedIndex < 0) selectedIndex = 0;

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 12,
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const BrandWordmark(compact: true),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                user.operationalContextLabel,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ],
        ),
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
          TextButton.icon(
            onPressed: () => context.go(NavigationMemory.storeTarget),
            icon: const Icon(Icons.storefront_outlined, size: 20),
            label: const Text('Cambiar a tienda'),
          ),
          const SizedBox(width: 4),
        ],
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, color: AppColors.line),
        ),
      ),
      body: child,
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: AppColors.line)),
        ),
        child: NavigationBar(
          selectedIndex: selectedIndex,
          onDestinationSelected: (index) {
            context.go(destinations[index].location);
          },
          destinations: destinations
              .map(
                (destination) => NavigationDestination(
                  icon: Icon(destination.icon),
                  selectedIcon: Icon(destination.selectedIcon),
                  label: destination.label,
                ),
              )
              .toList(),
        ),
      ),
    );
  }
}

class _PanelDestination {
  const _PanelDestination({
    required this.location,
    required this.label,
    required this.icon,
    required this.selectedIcon,
  });

  final String location;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}
