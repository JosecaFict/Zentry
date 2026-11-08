import 'dart:async';
import 'dart:io';

import 'package:capricho_store/core/network/api_exception.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:share_plus/share_plus.dart';

import 'assistant_api.dart';
import 'assistant_text.dart';

class AssistantScreen extends ConsumerStatefulWidget {
  const AssistantScreen({super.key, required this.mode});

  final AssistantMode mode;

  @override
  ConsumerState<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends ConsumerState<AssistantScreen> {
  final _draft = TextEditingController();
  final _scroll = ScrollController();
  late final AppLifecycleListener _lifecycle;
  AudioRecorder? _recorder;
  Timer? _recordingLimit;
  AssistantConversation? _conversation;
  List<AssistantMessage> _messages = [];
  bool _busy = true;
  bool _loadFailed = false;
  bool _recording = false;
  bool _voiceBusy = false;
  bool _exporting = false;
  String? _error;
  String? _pendingQuestion;

  AssistantApi get _api => ref.read(assistantApiProvider);
  bool get _customer => widget.mode == AssistantMode.customer;
  bool get _canNavigate => !_busy && !_recording && !_voiceBusy && !_exporting;
  bool get _canWrite => !_loadFailed && _conversation?.archived != true;
  bool get _supportsVoice =>
      _customer &&
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS);

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(
      onPause: () => unawaited(_finishVoice(discard: true)),
    );
    unawaited(_restore());
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    _recordingLimit?.cancel();
    final recorder = _recorder;
    if (recorder != null) unawaited(recorder.dispose());
    _draft.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _restore() async {
    await _run(() async {
      final history = await _api.conversations(widget.mode);
      if (!mounted) return;
      for (final conversation in history) {
        if (!conversation.archived) {
          await _open(conversation);
          break;
        }
      }
      if (mounted) setState(() => _loadFailed = false);
    }, loading: true);
  }

  Future<void> _open(AssistantConversation conversation) async {
    final messages = await _api.messages(conversation.id);
    if (!mounted) return;
    setState(() {
      _conversation = conversation;
      _messages = messages;
      _loadFailed = false;
    });
    _scrollToLatest();
  }

  Future<void> _run(
    Future<void> Function() operation, {
    bool loading = false,
  }) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await operation();
    } catch (error) {
      if (mounted) {
        setState(() {
          _loadFailed = loading;
          _error = _message(
            error,
            'No pudimos completar la consulta. Intenta nuevamente.',
          );
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _send() async {
    final content = _draft.text.trim();
    if (!_canNavigate || !_canWrite || content.isEmpty) return;
    setState(() => _pendingQuestion = content);
    _scrollToLatest();
    await _run(() async {
      final api = _api;
      final conversation = _conversation ?? await api.create(widget.mode);
      if (!mounted) return;
      setState(() => _conversation = conversation);
      final exchange = await api.send(conversation.id, content);
      if (!mounted) return;
      _draft.clear();
      setState(() => _messages = [..._messages, ...exchange]);
    });
    if (!mounted) return;
    setState(() => _pendingQuestion = null);
    _scrollToLatest();
  }

  void _scrollToLatest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scroll.hasClients) {
        unawaited(
          _scroll.animateTo(
            _scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 180),
            curve: Curves.easeOut,
          ),
        );
      }
    });
  }

  void _newConversation() {
    setState(() {
      _conversation = null;
      _messages = [];
      _error = null;
      _loadFailed = false;
    });
  }

  Future<void> _history() => _run(() async {
    final history = await _api.conversations(widget.mode);
    if (!mounted) return;
    final selected = await showModalBottomSheet<AssistantConversation>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(title: Text('Conversaciones')),
            if (history.isEmpty)
              const ListTile(title: Text('Todavía no tienes conversaciones.')),
            for (final item in history)
              ListTile(
                leading: Icon(
                  item.archived
                      ? Icons.archive_outlined
                      : Icons.chat_bubble_outline,
                ),
                title: Text(
                  item.updatedAt == null
                      ? 'Conversación'
                      : DateFormat('dd/MM/yyyy HH:mm')
                            .format(item.updatedAt!.toLocal()),
                ),
                subtitle: Text(item.archived ? 'Archivada' : 'Activa'),
                selected: item.id == _conversation?.id,
                onTap: () => Navigator.pop(context, item),
              ),
          ],
        ),
      ),
    );
    if (mounted && selected != null) await _open(selected);
  });

  Future<void> _archive() async {
    final conversation = _conversation;
    if (conversation == null || conversation.archived || !_canNavigate) return;
    await _run(() async {
      await _api.archive(conversation.id);
      if (mounted) _newConversation();
    });
  }

  Future<void> _startVoice() async {
    if (!_supportsVoice || !_canNavigate || !_canWrite) return;
    setState(() {
      _voiceBusy = true;
      _error = null;
    });
    final recorder = _recorder ??= AudioRecorder();
    try {
      if (!await recorder.hasPermission()) {
        throw const ApiException(
          'Habilita el micrófono para dictar tu consulta.',
        );
      }
      final directory = await getTemporaryDirectory();
      if (!mounted) return;
      await recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          numChannels: 1,
        ),
        path: path.join(
          directory.path,
          'zentry-voice-${DateTime.now().microsecondsSinceEpoch}.m4a',
        ),
      );
      if (!mounted) return;
      setState(() => _recording = true);
      _recordingLimit = Timer(
        const Duration(minutes: 1),
        () => unawaited(_finishVoice()),
      );
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = _message(error, 'No pudimos iniciar la grabación.'),
        );
      }
    } finally {
      if (mounted) setState(() => _voiceBusy = false);
    }
  }

  Future<void> _finishVoice({bool discard = false}) async {
    if (!_recording || _voiceBusy) return;
    _recordingLimit?.cancel();
    setState(() {
      _recording = false;
      _voiceBusy = true;
    });
    String? audio;
    try {
      if (discard) {
        await _recorder!.cancel();
        return;
      }
      audio = await _recorder!.stop();
      if (!mounted) return;
      if (audio == null) {
        throw const ApiException(
          'No se capturó audio. Intenta grabar otra vez.',
        );
      }
      final transcript = (await _api.transcribe(audio)).trim();
      if (!mounted) return;
      if (transcript.isEmpty) {
        throw const ApiException(
          'No pudimos reconocer palabras en la grabación.',
        );
      }
      final combined = _draft.text.trim().isEmpty
          ? transcript
          : '${_draft.text.trim()} $transcript';
      final text = combined.length > 4000
          ? combined.substring(0, 4000)
          : combined;
      _draft.value = TextEditingValue(
        text: text,
        selection: TextSelection.collapsed(offset: text.length),
      );
    } catch (error) {
      if (mounted) {
        setState(
          () =>
              _error = _message(error, 'No pudimos transcribir la grabación.'),
        );
      }
    } finally {
      if (audio != null) {
        try {
          await File(audio).delete();
        } on FileSystemException {
          // The operating system can clear the temporary directory.
        }
      }
      if (mounted) setState(() => _voiceBusy = false);
    }
  }

  Future<void> _export(
    BuildContext buttonContext,
    AssistantMessage message,
    String format,
  ) async {
    final conversation = _conversation;
    if (conversation == null ||
        !_canNavigate ||
        !message.exportable ||
        _customer) {
      return;
    }
    final box = buttonContext.findRenderObject() as RenderBox?;
    final origin = box != null && box.hasSize
        ? box.localToGlobal(Offset.zero) & box.size
        : null;
    setState(() {
      _exporting = true;
      _error = null;
    });
    try {
      final bytes = await _api.export(conversation.id, message.id, format);
      if (!mounted) return;
      await SharePlus.instance.share(
        ShareParams(
          files: [
            XFile.fromData(
              bytes,
              mimeType: format == 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ),
          ],
          fileNameOverrides: ['reporte-${message.id}.$format'],
          sharePositionOrigin: origin,
        ),
      );
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = _message(error, 'No pudimos descargar el reporte.'),
        );
      }
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  String _message(Object error, String fallback) =>
      error is ApiException ? error.message : fallback;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.mode.title),
        actions: [
          IconButton(
            tooltip: 'Historial',
            icon: const Icon(Icons.history),
            onPressed: _canNavigate ? _history : null,
          ),
          PopupMenuButton<String>(
            tooltip: 'Opciones de conversación',
            enabled: _canNavigate,
            onSelected: (action) {
              if (action == 'archive') {
                unawaited(_archive());
              } else {
                _newConversation();
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'new',
                child: Text('Nueva conversación'),
              ),
              if (_conversation != null && !_conversation!.archived)
                const PopupMenuItem(
                  value: 'archive',
                  child: Text('Archivar conversación'),
                ),
            ],
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            children: [
              if ((_busy && _pendingQuestion == null) || _exporting)
                const LinearProgressIndicator(),
              Expanded(
                child: ListView(
                  controller: _scroll,
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_messages.isEmpty &&
                        _pendingQuestion == null &&
                        !_busy &&
                        !_loadFailed)
                      _emptyState(theme),
                    for (final message in _messages)
                      _messageCard(theme, message),
                    if (_pendingQuestion case final question?) ...[
                      _bubble(theme, question, true),
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 8),
                        child: Text('Preparando respuesta…'),
                      ),
                    ],
                  ],
                ),
              ),
              if (_error case final error?)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  child: Text(
                    error,
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                ),
              SafeArea(
                top: false,
                minimum: const EdgeInsets.fromLTRB(12, 6, 12, 10),
                child: _composer(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _emptyState(ThemeData theme) {
    final prompt = _customer
        ? '¿Hay promociones hoy?'
        : '¿Cuál fue la prenda más vendida este mes?';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _customer ? '¿Qué prenda buscas?' : '¿Qué quieres consultar?',
          style: theme.textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          _customer
              ? 'Consulta tallas, colores, precios y promociones de esta tienda.'
              : 'Consulta ventas e inventario de tu empresa. Los reportes dependen de tu plan y permisos.',
        ),
        const SizedBox(height: 12),
        ActionChip(
          label: Text(prompt),
          onPressed: _canWrite ? () => _draft.text = prompt : null,
        ),
      ],
    );
  }

  Widget _composer() {
    if (_loadFailed) {
      return OutlinedButton(
        onPressed: _busy ? null : _restore,
        child: const Text('Reintentar'),
      );
    }
    if (_conversation?.archived == true) {
      return const Text('Esta conversación está archivada.');
    }
    if (_recording) {
      return Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 8,
        children: [
          const Text('Grabando…'),
          TextButton(
            onPressed: () => _finishVoice(discard: true),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: _finishVoice,
            child: const Text('Transcribir'),
          ),
        ],
      );
    }
    if (_voiceBusy) return const Text('Procesando el dictado…');
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        if (_supportsVoice)
          IconButton(
            tooltip: 'Dictar consulta',
            onPressed: _canNavigate ? _startVoice : null,
            icon: const Icon(Icons.mic_none),
          ),
        Expanded(
          child: TextField(
            controller: _draft,
            readOnly: !_canNavigate,
            minLines: 1,
            maxLines: 4,
            maxLength: 4000,
            decoration: const InputDecoration(
              labelText: 'Escribe tu consulta',
              counterText: '',
            ),
          ),
        ),
        IconButton(
          tooltip: 'Enviar consulta',
          onPressed: _canNavigate ? _send : null,
          icon: const Icon(Icons.send_rounded),
        ),
      ],
    );
  }

  Widget _messageCard(ThemeData theme, AssistantMessage message) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _bubble(theme, message.content, message.fromUser),
      for (final product in message.products)
        _AssistantProductCard(product: product),
      if (!_customer && message.exportable)
        Wrap(
          spacing: 8,
          children: [
            for (final format in ['pdf', 'xlsx'])
              Builder(
                builder: (context) => OutlinedButton.icon(
                  onPressed: _canNavigate
                      ? () => _export(context, message, format)
                      : null,
                  icon: const Icon(Icons.download_outlined),
                  label: Text(format == 'pdf' ? 'PDF' : 'Excel'),
                ),
              ),
          ],
        ),
    ],
  );

  Widget _bubble(ThemeData theme, String content, bool fromUser) {
    final colors = theme.colorScheme;
    return Align(
      alignment: fromUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: fromUser ? colors.primary : colors.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
        ),
        child: AssistantText(
          content: content,
          fromUser: fromUser,
          style: theme.textTheme.bodyMedium?.copyWith(
            color: fromUser ? colors.onPrimary : colors.onSurface,
          ),
        ),
      ),
    );
  }
}

class _AssistantProductCard extends StatelessWidget {
  const _AssistantProductCard({required this.product});

  final Map<String, dynamic> product;

  String _money(Object? raw) {
    final value = num.tryParse(raw.toString());
    if (value == null) return '';
    return NumberFormat.currency(
      locale: 'es_BO',
      symbol: 'Bs ',
      decimalDigits: 2,
    ).format(value);
  }

  @override
  Widget build(BuildContext context) {
    final image = product['imagen_url'] as String?;
    final original = _money(product['precio_original']);
    final discount = num.tryParse('${product['descuento_porcentaje']}');
    final promotion = product['promocion_nombre'] as String?;
    final sizes = (product['tallas'] as List? ?? []).join(', ');
    final colors = (product['colores'] as List? ?? []).join(', ');
    return Card(
      child: InkWell(
        onTap: () => context.push('/productos/${product['id_producto']}'),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (image != null && image.isNotEmpty) ...[
                Image.network(
                  image,
                  width: 60,
                  height: 72,
                  fit: BoxFit.cover,
                  errorBuilder: (_, _, _) => const SizedBox(
                    width: 60,
                    height: 72,
                    child: Icon(Icons.checkroom_outlined),
                  ),
                ),
                const SizedBox(width: 12),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      product['nombre'] as String,
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    Text('${product['marca']} · ${product['categoria']}'),
                    Wrap(
                      spacing: 8,
                      children: [
                        if (original.isNotEmpty)
                          Text(
                            original,
                            style: const TextStyle(
                              decoration: TextDecoration.lineThrough,
                            ),
                          ),
                        Text(
                          _money(product['precio']),
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ],
                    ),
                    if (discount != null)
                      Text(
                        '${promotion ?? 'Oferta'} · −${NumberFormat.decimalPattern('es_BO').format(discount)}%',
                      )
                    else if (promotion != null)
                      Text(promotion),
                    if (sizes.isNotEmpty) Text('Tallas: $sizes'),
                    if (colors.isNotEmpty) Text('Colores: $colors'),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
