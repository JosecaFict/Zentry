import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';

abstract final class NavigationMemory {
  static String _storeLocation = '/inicio';
  static String _panelLocation = '/admin/resumen';

  static void rememberStore(String location) {
    if (_isStoreLocation(location)) _storeLocation = location;
  }

  static void rememberPanel(String location) {
    if (_isPanelLocation(location)) _panelLocation = location;
  }

  static String get storeTarget => _storeLocation;

  static String? panelRedirect({
    required bool initialized,
    required AppUser? user,
    required String location,
  }) {
    final path = Uri.parse(location).path;
    if (!initialized) return null;
    if (user == null) {
      final returnUrl = Uri.encodeComponent(location);
      return '/login?returnUrl=$returnUrl';
    }
    if (path == '/admin/403') return null;
    if (!user.canAccessOperationalPanel) return '/admin/403';
    if (path == '/admin') return panelTarget(user);
    if (!canOpenPanelLocation(user, path)) return '/admin/403';
    return null;
  }

  static String panelTarget(AppUser user) {
    if (canOpenPanelLocation(user, _panelLocation)) return _panelLocation;
    if (user.canAccessSection(OperationalSection.summary)) {
      return '/admin/resumen';
    }
    if (user.canAccessSection(OperationalSection.inventory)) {
      return '/admin/inventario';
    }
    if (user.canAccessSection(OperationalSection.operations)) {
      return '/admin/operaciones';
    }
    return '/admin/perfil';
  }

  static bool canOpenPanelLocation(AppUser user, String location) {
    if (location == '/admin/offline') return user.canOpenOffline;
    if (location.startsWith('/admin/inventario')) {
      return user.canAccessSection(OperationalSection.inventory);
    }
    if (location.startsWith('/admin/operaciones')) {
      return user.canAccessSection(OperationalSection.operations);
    }
    if (location.startsWith('/admin/perfil')) {
      return user.canAccessSection(OperationalSection.account);
    }
    if (location.startsWith('/admin/resumen')) {
      return user.canAccessSection(OperationalSection.summary);
    }
    return false;
  }

  static bool _isStoreLocation(String location) =>
      location == '/inicio' ||
      location == '/catalogo' ||
      location == '/cuenta' ||
      location.startsWith('/productos/');

  static bool _isPanelLocation(String location) =>
      location.startsWith('/admin/') && location != '/admin/403';
}
