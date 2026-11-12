import 'dart:async';

import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeProbe implements NetworkProbe {
  bool interface = true;
  bool backend = true;
  bool unmetered = true;
  int pings = 0;
  final StreamController<bool> changes = StreamController.broadcast();

  @override
  Stream<bool> get interfaceChanges => changes.stream;

  @override
  Future<bool> hasInterface() async => interface;

  @override
  Future<bool> onUnmeteredNetwork() async => unmetered;

  @override
  Future<bool> reachesBackend() async {
    pings++;
    return backend;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late FakeProbe probe;
  late ProviderContainer container;

  setUp(() {
    probe = FakeProbe();
    container = ProviderContainer(
      overrides: [networkProbeProvider.overrideWithValue(probe)],
    );
    container.listen(connectivityControllerProvider, (_, _) {});
  });

  tearDown(() {
    container.dispose();
    probe.changes.close();
  });

  ConnectivityState read() => container.read(connectivityControllerProvider);
  ConnectivityController controller() =>
      container.read(connectivityControllerProvider.notifier);

  test('al iniciar verifica y queda en línea', () async {
    expect(read().checked, isFalse);
    await controller().check();
    expect(read().checked, isTrue);
    expect(read().online, isTrue);
    expect(read().offlineSince, isNull);
  });

  test('con wifi pero sin respuesta del backend queda sin conexión', () async {
    probe.backend = false;
    await controller().check();
    expect(read().online, isFalse);
    expect(read().offlineSince, isNotNull);
  });

  test('sin interfaz de red no hace ping', () async {
    await controller().check();
    final before = probe.pings;
    probe.interface = false;
    await controller().check();
    expect(read().online, isFalse);
    expect(probe.pings, before);
  });

  test('un cambio de red verifica de inmediato', () async {
    await controller().check();
    probe.backend = false;
    probe.changes.add(true);
    await pumpEventQueue();
    expect(read().online, isFalse);

    probe.backend = true;
    probe.changes.add(true);
    await pumpEventQueue();
    expect(read().online, isTrue);
  });

  test(
    'mantiene la hora del primer corte mientras sigue sin conexión',
    () async {
      probe.backend = false;
      await controller().check();
      final since = read().offlineSince;
      await controller().check();
      expect(read().offlineSince, since);
    },
  );

  test('cada chequeo cambia checkedAt (dispara la sincronización)', () async {
    await controller().check();
    final first = read().checkedAt;
    await Future<void>.delayed(const Duration(milliseconds: 2));
    await controller().check();
    expect(read().checkedAt, isNot(first));
  });

  test('chequeos simultáneos hacen un solo ping', () async {
    await controller().check();
    final before = probe.pings;
    await Future.wait([controller().check(), controller().check()]);
    expect(probe.pings, before + 1);
  });
}
