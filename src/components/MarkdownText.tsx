import React from 'react';
import { Text, TextStyle, StyleSheet, StyleProp, Platform } from 'react-native';

interface MarkdownTextProps {
  content: string;
  style?: StyleProp<TextStyle>;
  actionStyle?: StyleProp<TextStyle>;
  boldStyle?: StyleProp<TextStyle>;
  numberOfLines?: number;
}

/**
 * Native lightweight Markdown parser for Character / AI text.
 * Handles:
 * - *asterisk actions / italics*
 * - **bold speech / text**
 * - ***bold italic***
 * - _underscore italics_
 * - `inline code`
 */
export default function MarkdownText({
  content,
  style,
  actionStyle,
  boldStyle,
  numberOfLines,
}: MarkdownTextProps) {
  if (!content) return null;

  // Tokenize regex matching bold-italic, bold, italic (asterisk and underscore), and inline code
  // 1: ***bold italic***
  // 2: **bold**
  // 3: *italic/action*
  // 4: _italic_
  // 5: `code`
  const regex = /(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_|`[^`]+`)/g;
  const parts = content.split(regex);

  return (
    <Text style={[styles.defaultBase, style]} numberOfLines={numberOfLines}>
      {parts.map((part, index) => {
        if (!part) return null;

        // Bold Italic: ***text***
        if (part.startsWith('***') && part.endsWith('***') && part.length >= 6) {
          const inner = part.slice(3, -3);
          return (
            <Text
              key={index}
              style={[styles.bold, styles.italic, boldStyle, actionStyle]}
            >
              {inner}
            </Text>
          );
        }

        // Bold: **text**
        if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
          const inner = part.slice(2, -2);
          return (
            <Text key={index} style={[styles.bold, boldStyle]}>
              {inner}
            </Text>
          );
        }

        // Italic / Action: *text*
        if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
          const inner = part.slice(1, -1);
          return (
            <Text key={index} style={[styles.italic, styles.actionColor, actionStyle]}>
              {inner}
            </Text>
          );
        }

        // Underscore Italic: _text_
        if (part.startsWith('_') && part.endsWith('_') && part.length >= 2) {
          const inner = part.slice(1, -1);
          return (
            <Text key={index} style={[styles.italic, actionStyle]}>
              {inner}
            </Text>
          );
        }

        // Inline Code: `text`
        if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
          const inner = part.slice(1, -1);
          return (
            <Text key={index} style={styles.inlineCode}>
              {inner}
            </Text>
          );
        }

        // Normal text
        return <Text key={index}>{part}</Text>;
      })}
    </Text>
  );
}

const styles = StyleSheet.create({
  defaultBase: {
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 21,
  },
  bold: {
    fontWeight: '700',
    color: '#FFFFFF',
  },
  italic: {
    fontStyle: 'italic',
  },
  actionColor: {
    color: '#D4D4D8',
  },
  inlineCode: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    backgroundColor: '#1E1E24',
    color: '#F43F5E',
    paddingHorizontal: 4,
    borderRadius: 4,
  },
});
