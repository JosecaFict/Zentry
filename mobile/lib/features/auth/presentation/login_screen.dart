import 'package:capricho_store/app/navigation_memory.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:capricho_store/features/auth/presentation/auth_controller.dart';
import 'package:capricho_store/shared/widgets/brand_wordmark.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

/// [CU-01] Pantalla de Inicio de Sesión (Login) y acceso a panel operativo
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final formKey = GlobalKey<FormState>();
  final email = TextEditingController();
  final password = TextEditingController();
  bool hidden = true;

  @override
  void initState() {
    super.initState();
    email.addListener(_onFieldChanged);
    password.addListener(_onFieldChanged);
    // Limpiar errores previos y asegurar que loading esté en false
    Future.microtask(() {
      ref.read(authControllerProvider.notifier).clearError();
    });
  }

  void _onFieldChanged() {
    ref.read(authControllerProvider.notifier).clearError();
  }

  @override
  void dispose() {
    email.removeListener(_onFieldChanged);
    password.removeListener(_onFieldChanged);
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    FocusScope.of(context).unfocus();
    if (!formKey.currentState!.validate()) {
      HapticFeedback.mediumImpact();
      return;
    }
    if (ref.read(authControllerProvider).loading) return;

    HapticFeedback.lightImpact();
    final success = await ref
        .read(authControllerProvider.notifier)
        .login(email.text.trim(), password.text);

    if (!mounted) return;

    if (success) {
      HapticFeedback.lightImpact();
      final requestedLocation = GoRouterState.of(context)
          .uri
          .queryParameters['returnUrl'];
      final safeReturnUrl =
          requestedLocation != null &&
              requestedLocation.startsWith('/') &&
              !requestedLocation.startsWith('//')
          ? requestedLocation
          : null;
      final loggedUser = ref.read(authControllerProvider).user;
      if (safeReturnUrl != null) {
        context.go(safeReturnUrl);
      } else if (loggedUser != null && loggedUser.canAccessOperationalPanel) {
        context.go(NavigationMemory.panelTarget(loggedUser));
      } else {
        context.go('/cuenta');
      }
    } else {
      HapticFeedback.mediumImpact();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authControllerProvider);

    return Scaffold(
      appBar: AppBar(
        leading: const BackButton(),
        actions: [
          TextButton.icon(
            onPressed: () async {
              await ref.read(authControllerProvider.notifier).logout();
              await ref.read(tenantControllerProvider.notifier).clear();
              if (context.mounted) context.go('/empresa');
            },
            icon: const Icon(Icons.storefront_outlined, size: 18),
            label: const Text('Cambiar empresa'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 12, 24, 32),
            child: Form(
              key: formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const BrandWordmark(),
                  const SizedBox(height: 34),
                  Text(
                    'Ingresa a ${ref.watch(tenantControllerProvider).selected?.name ?? 'tu empresa'}',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Ingresa para consultar tu perfil y continuar tu experiencia.',
                  ),
                  if (state.sessionExpired) ...[
                    const SizedBox(height: 20),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.amber.shade100,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.amber.shade700),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.info_outline,
                            color: Colors.amber.shade900,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'Tu sesión ha expirado. Por favor ingresa nuevamente.',
                              style: TextStyle(
                                color: Colors.amber.shade900,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 24),
                  TextFormField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Correo electrónico',
                      prefixIcon: Icon(Icons.mail_outline_rounded),
                    ),
                    validator: (value) => value != null && value.contains('@')
                        ? null
                        : 'Ingresa un correo válido.',
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: password,
                    obscureText: hidden,
                    autofillHints: const [AutofillHints.password],
                    textInputAction: TextInputAction.done,
                    onFieldSubmitted: (_) => submit(),
                    decoration: InputDecoration(
                      labelText: 'Contraseña',
                      prefixIcon: const Icon(Icons.lock_outline_rounded),
                      suffixIcon: IconButton(
                        tooltip: hidden
                            ? 'Mostrar contraseña'
                            : 'Ocultar contraseña',
                        onPressed: () => setState(() => hidden = !hidden),
                        icon: Icon(
                          hidden
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                      ),
                    ),
                    validator: (value) => (value?.length ?? 0) >= 1
                        ? null
                        : 'Ingresa tu contraseña.',
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () => context.push('/recuperar-password'),
                      child: const Text('¿Olvidaste tu contraseña?'),
                    ),
                  ),
                  if (state.error != null && !state.sessionExpired) ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.error
                            .withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: Theme.of(context).colorScheme.error
                              .withValues(alpha: 0.25),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                state.error!.toLowerCase().contains('bloquead')
                                    ? Icons.lock_person_rounded
                                    : (state.error!.toLowerCase().contains('pausada')
                                        ? Icons.lock_clock_rounded
                                        : Icons.error_outline_rounded),
                                size: 20,
                                color: Theme.of(context).colorScheme.error,
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  state.error!,
                                  style: TextStyle(
                                    color: Theme.of(context).colorScheme.error,
                                    fontWeight: FontWeight.w600,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          if (state.error!.toLowerCase().contains('bloquead') ||
                              state.error!.toLowerCase().contains('recuperar')) ...[
                            const SizedBox(height: 8),
                            Align(
                              alignment: Alignment.centerRight,
                              child: TextButton.icon(
                                style: TextButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 10,
                                    vertical: 4,
                                  ),
                                  visualDensity: VisualDensity.compact,
                                  foregroundColor:
                                      Theme.of(context).colorScheme.error,
                                ),
                                onPressed: () =>
                                    context.push('/recuperar-password'),
                                icon: const Icon(Icons.key_rounded, size: 16),
                                label: const Text(
                                  'Recuperar contraseña ahora',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: state.loading ? null : submit,
                    child: state.loading
                        ? const SizedBox.square(
                            dimension: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Ingresar'),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text('¿Aún no tienes cuenta?'),
                      TextButton(
                        onPressed: () => context.push('/registro'),
                        child: const Text('Crear una cuenta'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
