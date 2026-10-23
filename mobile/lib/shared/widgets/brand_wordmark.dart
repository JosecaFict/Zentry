import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/core/tenant/tenant_context.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class BrandWordmark extends ConsumerWidget {
  const BrandWordmark({
    this.compact = false,
    this.white = false,
    super.key,
  });

  final bool compact;
  final bool white;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tenant = ref.watch(tenantControllerProvider).selected;
    final targetHeight = compact ? 34.0 : 78.0;

    return Semantics(
      header: true,
      label: tenant?.name ?? 'Zentry',
      child: tenant?.logoUrl != null && tenant!.logoUrl!.isNotEmpty
          ? Image.network(
              tenant.logoUrl!,
              height: targetHeight,
              fit: BoxFit.contain,
              alignment: Alignment.centerLeft,
              errorBuilder: (_, _, _) => _fallbackWordmark(tenant?.name),
            )
          : _fallbackWordmark(tenant?.name),
    );
  }

  Widget _fallbackWordmark(String? name) => Column(
    mainAxisSize: MainAxisSize.min,
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        name ?? 'Zentry',
        style: TextStyle(
          color: white ? Colors.white : AppColors.ink,
          fontSize: compact ? 17 : 28,
          height: 0.92,
          fontWeight: FontWeight.w900,
          letterSpacing: compact ? -0.5 : -1.0,
        ),
      ),
    ],
  );
}

