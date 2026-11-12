import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Envuelve una pantalla que no funciona sin internet (asesor, probador,
/// pago). Si se entra sin conexión muestra un mensaje claro en lugar de
/// fallar, y abre la pantalla real sola cuando vuelve la señal.
///
/// Una vez abierta, no se cierra si la conexión cae unos segundos: así no se
/// interrumpe a quien está pagando o usando la cámara.
class RequiresConnection extends ConsumerStatefulWidget {
  const RequiresConnection({
    required this.feature,
    required this.child,
    super.key,
  });

  /// Nombre de la función, ej. "El asesor".
  final String feature;
  final Widget child;

  @override
  ConsumerState<RequiresConnection> createState() => _RequiresConnectionState();
}

class _RequiresConnectionState extends ConsumerState<RequiresConnection> {
  bool _opened = false;

  @override
  Widget build(BuildContext context) {
    final connectivity = ref.watch(connectivityControllerProvider);
    if (_opened || !connectivity.checked || connectivity.online) {
      _opened = true;
      return widget.child;
    }
    return Scaffold(
      appBar: AppBar(),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off_outlined,
                size: 56,
                color: AppColors.warning,
              ),
              const SizedBox(height: 16),
              Text(
                '${widget.feature} necesita conexión',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              const Text(
                'Se abrirá automáticamente cuando vuelva la señal.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              OutlinedButton.icon(
                onPressed: () =>
                    ref.read(connectivityControllerProvider.notifier).check(),
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Reintentar ahora'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
