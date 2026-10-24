import 'dart:async';

import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

class CompanySelectionScreen extends ConsumerStatefulWidget {
  const CompanySelectionScreen({super.key});

  @override
  ConsumerState<CompanySelectionScreen> createState() =>
      _CompanySelectionScreenState();
}

class _CompanySelectionScreenState
    extends ConsumerState<CompanySelectionScreen> {
  final _search = TextEditingController();
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(tenantControllerProvider.notifier).search(''),
    );
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _changed(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      ref.read(tenantControllerProvider.notifier).search(value);
    });
  }

  Future<void> _select(TenantIdentity tenant) async {
    await ref.read(tenantControllerProvider.notifier).select(tenant);
    if (mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tenantControllerProvider);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(24, 32, 24, 40),
              children: [
                Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.asset(
                        'assets/images/zentry-mark.png',
                        width: 44,
                        height: 44,
                        fit: BoxFit.cover,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Text(
                      'Zentry',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
                    ),
                  ],
                ),
                const SizedBox(height: 56),
                Text(
                  '¿Qué tienda estás buscando?',
                  style: Theme.of(context).textTheme.displaySmall,
                ),
                const SizedBox(height: 12),
                const Text(
                  'Busca y selecciona una tienda para explorar sus productos y realizar tus compras.',
                ),
                const SizedBox(height: 28),
                TextField(
                  controller: _search,
                  onChanged: _changed,
                  textInputAction: TextInputAction.search,
                  decoration: const InputDecoration(
                    labelText: 'Buscar tiendas',
                    hintText: 'Ej. Capricho Store',
                    prefixIcon: Icon(Icons.search_rounded),
                  ),
                ),
                const SizedBox(height: 20),
                if (!state.loading && state.results.isNotEmpty) ...[
                  Text(
                    _search.text.trim().isEmpty
                        ? 'Tiendas disponibles'
                        : 'Resultados',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 12),
                ],
                if (state.loading)
                  const Center(child: CircularProgressIndicator())
                else if (state.error != null)
                  _Message(text: state.error!, error: true)
                else if (state.results.isEmpty)
                  const _Message(
                    text: 'No encontramos una tienda con ese nombre.',
                  )
                else
                  ...state.results.map(
                    (tenant) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Card(
                        child: ListTile(
                          contentPadding: const EdgeInsets.all(14),
                          leading: _TenantLogo(tenant: tenant),
                          title: Text(
                            tenant.name,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          subtitle: Text(tenant.slug),
                          trailing: const Icon(Icons.arrow_forward_rounded),
                          onTap: () => _select(tenant),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TenantLogo extends StatelessWidget {
  const _TenantLogo({required this.tenant});
  final TenantIdentity tenant;

  @override
  Widget build(BuildContext context) {
    final fallback = CircleAvatar(
      backgroundColor: tenant.color,
      foregroundColor: Colors.white,
      child: Text(tenant.name.substring(0, 1).toUpperCase()),
    );
    if (tenant.logoUrl == null || tenant.logoUrl!.isEmpty) return fallback;
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: Image.network(
        tenant.logoUrl!,
        width: 48,
        height: 48,
        fit: BoxFit.contain,
        errorBuilder: (_, _, _) => fallback,
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.text, this.error = false});
  final String text;
  final bool error;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: error ? const Color(0xFFFFE9E7) : AppColors.muted,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(text),
      );
}
