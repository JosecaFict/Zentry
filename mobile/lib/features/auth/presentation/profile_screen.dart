import 'package:capricho_store/app/navigation_memory.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/features/commerce/presentation/commerce_controller.dart';
import 'package:capricho_store/shared/widgets/adaptive/adaptive_dialogs.dart';
import 'package:capricho_store/shared/widgets/brand_wordmark.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(authControllerProvider);

    if (!state.initialized) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final user = state.user;

    return Scaffold(
      appBar: AppBar(
        title: const BrandWordmark(compact: true),
        centerTitle: false,
        actions: [
          if (user != null)
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
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(color: AppColors.line, height: 1),
        ),
      ),
      body: user == null
          ? _buildGuestView(context, ref)
          : _buildAuthenticatedView(context, ref, user),
    );
  }

  Widget _buildGuestView(BuildContext context, WidgetRef ref) {
    final company = ref.watch(tenantControllerProvider).selected?.name ?? 'tu empresa';
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
        children: [
          const SizedBox(height: 20),
          Center(
            child: Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primaryContainer
                    .withValues(alpha: 0.35),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.person_outline_rounded,
                size: 64,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Bienvenido a tu espacio',
            style: Theme.of(context).textTheme.headlineMedium
                ?.copyWith(fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 10),
          Text(
            'Inicia sesión para gestionar tus datos de cliente, consultar tu cuenta y disfrutar de la experiencia de $company.',
            style: TextStyle(color: Colors.grey.shade700, height: 1.3),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          FilledButton.icon(
            onPressed: () => context.push('/login'),
            icon: const Icon(Icons.login_rounded),
            label: const Text('Iniciar sesión'),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: () => context.push('/registro'),
            icon: const Icon(Icons.person_add_outlined),
            label: const Text('Crear cuenta nueva'),
          ),
          const SizedBox(height: 32),
          const Divider(),
          const SizedBox(height: 16),
          Text(
            '¿Qué puedes hacer en $company?',
            style: Theme.of(context).textTheme.titleSmall
                ?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          _buildBenefitItem(
            context,
            icon: Icons.checkroom_outlined,
            title: 'Catálogo de prendas exclusivas',
            subtitle:
                'Explora poleras, camisas, blusas y polos por talla y color.',
          ),
          _buildBenefitItem(
            context,
            icon: Icons.straighten_outlined,
            title: 'Guía de medidas detallada',
            subtitle:
                'Consulta medidas reales de hombros, pecho, largo y manga.',
          ),
          _buildBenefitItem(
            context,
            icon: Icons.security_outlined,
            title: 'Seguridad y privacidad',
            subtitle: 'Tus credenciales y datos personales protegidos.',
          ),
        ],
      ),
    );
  }

  Widget _buildBenefitItem(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String subtitle,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              icon,
              size: 20,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
                Text(
                  subtitle,
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAuthenticatedView(
    BuildContext context,
    WidgetRef ref,
    AppUser user,
  ) {
    final trimmedNames = user.names.trim();
    final initials = trimmedNames.isNotEmpty
        ? trimmedNames.substring(0, 1).toUpperCase()
        : 'U';

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
      children: [
        // Cabecera con Avatar
        Center(
          child: Column(
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    width: 88,
                    height: 88,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          Theme.of(context).colorScheme.primary,
                          Theme.of(context).colorScheme.secondary,
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: Theme.of(context)
                              .colorScheme
                              .primary
                              .withValues(alpha: 0.25),
                          blurRadius: 10,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: ClipOval(
                      child: user.avatarUrl != null && user.avatarUrl!.isNotEmpty
                          ? CachedNetworkImage(
                              imageUrl: user.avatarUrl!,
                              fit: BoxFit.cover,
                              width: 88,
                              height: 88,
                              placeholder: (context, url) => Center(
                                child: SizedBox(
                                  width: 24,
                                  height: 24,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white.withValues(alpha: 0.8),
                                  ),
                                ),
                              ),
                              errorWidget: (context, url, error) => Center(
                                child: Text(
                                  initials,
                                  style: const TextStyle(
                                    fontSize: 34,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            )
                          : Center(
                              child: Text(
                                initials,
                                style: const TextStyle(
                                  fontSize: 34,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                    ),
                  ),
                  Positioned(
                    bottom: -2,
                    right: -2,
                    child: Material(
                      color: Theme.of(context).colorScheme.primary,
                      shape: const CircleBorder(),
                      elevation: 3,
                      child: InkWell(
                        customBorder: const CircleBorder(),
                        onTap: () => _showAvatarOptions(context, ref, user),
                        child: const Padding(
                          padding: EdgeInsets.all(7),
                          child: Icon(
                            Icons.camera_alt_rounded,
                            size: 16,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                user.fullName,
                style: Theme.of(context).textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 4),
              Text(
                user.email,
                style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: AppColors.muted,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.line),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      user.hasOperationalRole
                          ? Icons.shield_outlined
                          : Icons.check_circle_rounded,
                      size: 14,
                      color: user.hasOperationalRole
                          ? AppColors.cobalt
                          : const Color(0xFF10B981),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      '${user.roleName.toUpperCase()} · ${user.status.toUpperCase()}',
                      style: TextStyle(
                        color: user.hasOperationalRole
                            ? AppColors.cobalt
                            : const Color(0xFF10B981),
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (user.canAccessOperationalPanel) ...[
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.cobalt, width: 1.5),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: AppColors.cobalt.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.shield_outlined,
                        color: AppColors.cobalt,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Herramientas de trabajo',
                            style: TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 16,
                              color: AppColors.ink,
                            ),
                          ),
                          SizedBox(height: 4),
                          Text(
                            'Abre las funciones operativas autorizadas para tu cuenta.',
                            style: TextStyle(
                              fontSize: 14,
                              color: AppColors.inkSoft,
                              height: 1.35,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () =>
                      context.go(NavigationMemory.panelTarget(user)),
                  icon: const Icon(Icons.arrow_forward_rounded),
                  label: const Text('Ir al panel'),
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 20),

        // Tarjeta de información personal
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.badge_outlined, size: 20, color: AppColors.cobalt),
                      SizedBox(width: 8),
                      Text(
                        'Información personal',
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 13.5,
                          color: AppColors.ink,
                        ),
                      ),
                    ],
                  ),
                  InkWell(
                    onTap: () => _showEditProfileDialog(context, ref, user),
                    borderRadius: BorderRadius.circular(8),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.edit_outlined,
                            size: 15,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'Editar',
                            style: TextStyle(
                              fontSize: 12.5,
                              fontWeight: FontWeight.w700,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const Divider(height: 24),
              _InfoRow(label: 'Nombres', value: user.names),
              _InfoRow(label: 'Apellidos', value: user.surnames),
              _InfoRow(label: 'Correo', value: user.email),
              _InfoRow(label: 'Teléfono', value: user.phone ?? 'No registrado'),
              _InfoRow(
                label: 'CI',
                value: user.ci ?? 'No registrado',
                last: true,
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),

        // Mis Compras y Reservas
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: AppColors.line),
          ),
          child: Column(
            children: [
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.cobaltLight,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.inventory_2_outlined,
                      color: AppColors.cobalt, size: 20),
                ),
                title: const Text('Mis Pedidos y Seguimiento',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                subtitle: const Text('Seguimiento de compras y recibos de pago'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () {
                  HapticFeedback.selectionClick();
                  context.push('/pedidos');
                },
              ),
              const Divider(height: 1),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.cobaltLight,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.event_seat_outlined,
                      color: AppColors.cobalt, size: 20),
                ),
                title: const Text('Mis Reservas de Prendas',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                subtitle: const Text('Prendas apartadas para prueba o retiro'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () {
                  HapticFeedback.selectionClick();
                  context.push('/reservas');
                },
              ),
              const Divider(height: 1),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.cobaltLight,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.location_on_outlined,
                      color: AppColors.cobalt, size: 20),
                ),
                title: const Text('Mis Direcciones de Envío',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                subtitle: const Text('Direcciones guardadas para delivery'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () {
                  HapticFeedback.selectionClick();
                  context.push('/direcciones');
                },
              ),
              const Divider(height: 1),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.cobaltLight,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.notifications_outlined,
                      color: AppColors.cobalt, size: 20),
                ),
                title: const Text('Notificaciones',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                subtitle: const Text('Avisos de pedidos y reservas'),
                trailing: Consumer(
                  builder: (context, ref, _) {
                    final unread = ref.watch(unreadNotificationsCountProvider);
                    if (unread > 0) {
                      return Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppColors.cobalt,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              '$unread',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(Icons.chevron_right_rounded),
                        ],
                      );
                    }
                    return const Icon(Icons.chevron_right_rounded);
                  },
                ),
                onTap: () {
                  HapticFeedback.selectionClick();
                  context.push('/notificaciones');
                },
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),

        // Accesos rápidos
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: Colors.grey.shade200),
          ),
          child: Column(
            children: [
              ListTile(
                leading: const Icon(Icons.grid_view_rounded),
                title: const Text('Explorar Catálogo'),
                subtitle: const Text('Ver todas las prendas disponibles'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.go('/catalogo'),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.home_outlined),
                title: const Text('Ir al Inicio'),
                subtitle: const Text('Novedades y categorías destacadas'),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.go('/inicio'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        // Botón Cerrar Sesión
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(
            foregroundColor: Theme.of(context).colorScheme.error,
            side: BorderSide(color: Theme.of(context).colorScheme.error),
            padding: const EdgeInsets.symmetric(vertical: 12),
          ),
          onPressed: () => _showLogoutDialog(context, ref),
          icon: const Icon(Icons.logout_rounded),
          label: const Text('Cerrar sesión'),
        ),
        const SizedBox(height: 12),
        TextButton.icon(
          onPressed: () => _changeCompany(context, ref),
          icon: const Icon(Icons.storefront_outlined),
          label: const Text('Cambiar de empresa'),
        ),
      ],
    );
  }

  Future<void> _showEditProfileDialog(
    BuildContext context,
    WidgetRef ref,
    AppUser user,
  ) async {
    HapticFeedback.selectionClick();
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => _EditProfileDialog(user: user),
    );
  }

  Future<void> _showLogoutDialog(BuildContext context, WidgetRef ref) async {
    final confirmed = await AdaptiveDialogs.showConfirmation(
      context: context,
      title: '¿Cerrar sesión?',
      message: 'Tendrás que ingresar tus credenciales la próxima vez que desees acceder a tu cuenta.',
      confirmText: 'Cerrar sesión',
      cancelText: 'Cancelar',
      isDestructive: true,
    );

    if (confirmed == true) {
      await ref.read(authControllerProvider.notifier).logout();
    }
  }

  Future<void> _changeCompany(BuildContext context, WidgetRef ref) async {
    await ref.read(authControllerProvider.notifier).logout();
    await ref.read(tenantControllerProvider.notifier).clear();
    if (context.mounted) context.go('/empresa');
  }

  Future<void> _showAvatarOptions(
    BuildContext context,
    WidgetRef ref,
    AppUser user,
  ) async {
    final hasAvatar = user.avatarUrl != null && user.avatarUrl!.isNotEmpty;

    final action = await showModalBottomSheet<String>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 36,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const Text(
                'Foto de perfil',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: AppColors.muted,
                  child: Icon(Icons.photo_camera_rounded, color: AppColors.cobalt),
                ),
                title: const Text('Tomar foto con la cámara'),
                onTap: () => Navigator.of(ctx).pop('camera'),
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: AppColors.muted,
                  child: Icon(Icons.photo_library_rounded, color: AppColors.cobalt),
                ),
                title: const Text('Elegir de la galería'),
                onTap: () => Navigator.of(ctx).pop('gallery'),
              ),
              if (hasAvatar)
                ListTile(
                  leading: const CircleAvatar(
                    backgroundColor: Color(0xFFFFEEEE),
                    child: Icon(Icons.delete_outline_rounded, color: Colors.red),
                  ),
                  title: const Text('Eliminar foto actual', style: TextStyle(color: Colors.red)),
                  onTap: () => Navigator.of(ctx).pop('delete'),
                ),
            ],
          ),
        ),
      ),
    );

    if (action == null || !context.mounted) return;

    if (action == 'delete') {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Eliminar foto de perfil'),
          content: const Text('¿Estás seguro de que deseas eliminar tu foto de perfil?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              style: FilledButton.styleFrom(backgroundColor: Colors.red),
              child: const Text('Eliminar'),
            ),
          ],
        ),
      );

      if (confirmed == true && context.mounted) {
        final ok = await ref.read(authControllerProvider.notifier).deleteAvatar();
        if (context.mounted) {
          if (ok) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Foto de perfil eliminada.')),
            );
          } else {
            final err = ref.read(authControllerProvider).error ?? 'No se pudo eliminar la foto.';
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(err.replaceAll('ApiException: ', ''))),
            );
          }
        }
      }
    } else if (action == 'camera' || action == 'gallery') {
      try {
        final picker = ImagePicker();
        final source = action == 'camera' ? ImageSource.camera : ImageSource.gallery;
        final picked = await picker.pickImage(
          source: source,
          maxWidth: 1024,
          maxHeight: 1024,
          imageQuality: 85,
        );

        if (picked != null && context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Row(
                children: [
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  ),
                  SizedBox(width: 12),
                  Text('Actualizando foto de perfil...'),
                ],
              ),
              duration: Duration(seconds: 4),
            ),
          );

          final ok = await ref.read(authControllerProvider.notifier).uploadAvatar(picked.path);
          if (context.mounted) {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
            if (ok) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('¡Foto de perfil actualizada con éxito!')),
              );
            } else {
              final err = ref.read(authControllerProvider).error ?? 'No se pudo subir la foto.';
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(err.replaceAll('ApiException: ', ''))),
              );
            }
          }
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error al seleccionar imagen: $e')),
          );
        }
      }
    }
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value, this.last = false});

  final String label;
  final String value;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: last ? 0 : 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 90,
            child: Text(
              label,
              style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
              textAlign: TextAlign.end,
            ),
          ),
        ],
      ),
    );
  }
}

class _EditProfileDialog extends ConsumerStatefulWidget {
  const _EditProfileDialog({required this.user});

  final AppUser user;

  @override
  ConsumerState<_EditProfileDialog> createState() => _EditProfileDialogState();
}

class _EditProfileDialogState extends ConsumerState<_EditProfileDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _namesController;
  late final TextEditingController _surnamesController;
  late final TextEditingController _phoneController;
  late final TextEditingController _ciController;

  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _namesController = TextEditingController(text: widget.user.names);
    _surnamesController = TextEditingController(text: widget.user.surnames);
    _phoneController = TextEditingController(text: widget.user.phone ?? '');
    _ciController = TextEditingController(text: widget.user.ci ?? '');
  }

  @override
  void dispose() {
    _namesController.dispose();
    _surnamesController.dispose();
    _phoneController.dispose();
    _ciController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    final success = await ref.read(authControllerProvider.notifier).updateProfile(
          names: _namesController.text.trim(),
          surnames: _surnamesController.text.trim(),
          phone: _phoneController.text.trim().isEmpty
              ? null
              : _phoneController.text.trim(),
          ci: _ciController.text.trim().isEmpty
              ? null
              : _ciController.text.trim(),
        );

    if (!mounted) return;

    if (success) {
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Row(
            children: [
              Icon(Icons.check_circle_outline, color: Colors.white, size: 20),
              SizedBox(width: 8),
              Text('Perfil actualizado correctamente.'),
            ],
          ),
          backgroundColor: Color(0xFF10B981),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } else {
      final authError = ref.read(authControllerProvider).error;
      setState(() {
        _loading = false;
        _error = authError ?? 'No se pudo actualizar el perfil.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: const Row(
        children: [
          Icon(Icons.edit_note_rounded, color: AppColors.cobalt),
          SizedBox(width: 8),
          Text(
            'Editar perfil',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
        ],
      ),
      content: SizedBox(
        width: MediaQuery.of(context).size.width,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_error != null) ...[
                  Container(
                    padding: const EdgeInsets.all(10),
                    margin: const EdgeInsets.only(bottom: 12),
                    decoration: BoxDecoration(
                      color: AppColors.danger.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: AppColors.danger.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.error_outline,
                          color: AppColors.danger,
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _error!,
                            style: const TextStyle(
                              color: AppColors.danger,
                              fontSize: 12.5,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                TextFormField(
                  controller: _namesController,
                  decoration: const InputDecoration(
                    labelText: 'Nombres *',
                    hintText: 'Ej. Juan',
                    prefixIcon: Icon(Icons.person_outline, size: 20),
                  ),
                  textCapitalization: TextCapitalization.words,
                  validator: (v) {
                    final val = v?.trim() ?? '';
                    if (val.isEmpty) return 'Ingresa tus nombres';
                    if (val.length < 2) return 'Mínimo 2 caracteres';
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _surnamesController,
                  decoration: const InputDecoration(
                    labelText: 'Apellidos *',
                    hintText: 'Ej. Pérez',
                    prefixIcon: Icon(Icons.person_outline, size: 20),
                  ),
                  textCapitalization: TextCapitalization.words,
                  validator: (v) {
                    final val = v?.trim() ?? '';
                    if (val.isEmpty) return 'Ingresa tus apellidos';
                    if (val.length < 2) return 'Mínimo 2 caracteres';
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.muted,
                    borderRadius: BorderRadius.circular(10),
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
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              widget.user.email,
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: AppColors.inkSoft,
                              ),
                            ),
                            const SizedBox(height: 2),
                            const Text(
                              'El correo no se puede modificar por seguridad',
                              style: TextStyle(
                                fontSize: 11,
                                color: AppColors.inkSoft,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _phoneController,
                  decoration: const InputDecoration(
                    labelText: 'Teléfono / WhatsApp',
                    hintText: 'Ej. 70012345',
                    prefixIcon: Icon(Icons.phone_outlined, size: 20),
                  ),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _ciController,
                  decoration: const InputDecoration(
                    labelText: 'Cédula de Identidad (CI)',
                    hintText: 'Ej. 1234567-SC',
                    prefixIcon: Icon(Icons.credit_card_outlined, size: 20),
                  ),
                  textCapitalization: TextCapitalization.characters,
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _loading ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: _loading ? null : _save,
          child: _loading
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Text('Guardar cambios'),
        ),
      ],
    );
  }
}
