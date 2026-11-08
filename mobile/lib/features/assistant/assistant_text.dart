import 'package:flutter/material.dart';

class AssistantText extends StatelessWidget {
  const AssistantText({
    super.key,
    required this.content,
    required this.fromUser,
    this.style,
  });

  final String content;
  final bool fromUser;
  final TextStyle? style;

  static final _bold = RegExp(r'\*\*([^*]+)\*\*');
  static final _divider = RegExp(r'^:?-{3,}:?$');

  List<String> _cells(String line) => line
      .trim()
      .replaceFirst(RegExp(r'^\|'), '')
      .replaceFirst(RegExp(r'\|$'), '')
      .split('|')
      .map((value) => value.trim())
      .toList();

  Widget _text(String value) {
    final spans = <TextSpan>[];
    var offset = 0;
    for (final match in _bold.allMatches(value)) {
      spans.add(TextSpan(text: value.substring(offset, match.start)));
      spans.add(
        TextSpan(
          text: match.group(1),
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
      );
      offset = match.end;
    }
    spans.add(TextSpan(text: value.substring(offset)));
    return SelectableText.rich(TextSpan(style: style, children: spans));
  }

  @override
  Widget build(BuildContext context) {
    if (fromUser) return SelectableText(content, style: style);
    final lines = content.split('\n');
    final blocks = <Widget>[];
    final prose = <String>[];

    void flushProse() {
      final text = prose.join('\n').trim();
      if (text.isNotEmpty) blocks.add(_text(text));
      prose.clear();
    }

    var index = 0;
    while (index < lines.length) {
      final headings = _cells(lines[index]);
      final divider = index + 1 < lines.length
          ? _cells(lines[index + 1])
          : <String>[];
      if (headings.length < 2 ||
          headings.length != divider.length ||
          !divider.every(_divider.hasMatch)) {
        prose.add(lines[index++]);
        continue;
      }

      flushProse();
      index += 2;
      final rows = <DataRow>[];
      while (index < lines.length && lines[index].contains('|')) {
        final cells = _cells(lines[index++]);
        rows.add(
          DataRow(
            cells: [
              for (var column = 0; column < headings.length; column++)
                DataCell(_text(column < cells.length ? cells[column] : '')),
            ],
          ),
        );
      }
      blocks.add(
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            horizontalMargin: 8,
            columnSpacing: 16,
            columns: [
              for (final heading in headings) DataColumn(label: _text(heading)),
            ],
            rows: rows,
          ),
        ),
      );
    }
    flushProse();
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: blocks,
    );
  }
}
