import React from 'react';
import { Text, TextStyle, StyleSheet, StyleProp, Platform } from 'react-native';

interface MarkdownTextProps {
  content: string;
  style?: StyleProp<TextStyle>;
  actionStyle?: StyleProp<TextStyle>;
  boldStyle?: StyleProp<TextStyle>;
  dialogueStyle?: StyleProp<TextStyle>;
  numberOfLines?: number;
}

/**
 * Native lightweight roleplay & markdown parser for Character / AI text.
 * Handles:
 * - Spoken dialogue in quotes ("..." or “...”) -> upright, bright white (#FFFFFF)
 * - Actions / Atmosphere / Background narration -> italic, dim muted gray (#9CA3AF)
 * - *asterisk actions / italics* -> italic, dim muted gray (#9CA3AF)
 * - **bold speech / text** -> bold
 * - ***bold italic*** -> bold italic
 * - _underscore italics_ -> italic
 * - `inline code` -> code style
 */
export default function MarkdownText({
  content,
  style,
  actionStyle,
  boldStyle,
  dialogueStyle,
  numberOfLines,
}: MarkdownTextProps) {
  if (!content) return null;

  // 1. Detect if content contains spoken dialogue inside quotation marks (ASCII " or curly “ ” or « »)
  const hasQuotes = /([“"„«][^”"»]*[”"»])/.test(content);
  // 2. Detect if content contains explicit *action* or _action_
  const hasAsterisks = /(\*[^*]+\*|_[^_]+_)/.test(content);

  const tokens: Array<{
    type: 'dialogue' | 'action' | 'bold' | 'bold-action' | 'code';
    text: string;
  }> = [];

  if (hasQuotes) {
    // Quote-based novelistic dialogue format:
    // Text inside quotes is spoken dialogue (bright white, normal font).
    // Text outside quotes is atmosphere, actions, narration, and background (italic, dim color).
    const quoteRegex = /([“"„«][^”"»]*[”"»])/g;
    const segments = content.split(quoteRegex);

    for (const segment of segments) {
      if (!segment) continue;

      const isQuote =
        /^[“"„«].*[”"»]$/s.test(segment) && segment.length >= 2;

      if (isQuote) {
        // Dialogue: bright white, upright
        tokens.push({ type: 'dialogue', text: segment });
      } else {
        // Outside quotes: atmosphere / narration / actions / background!
        tokenizeMarkdown(segment, tokens, /* defaultToAction */ true);
      }
    }
  } else if (hasAsterisks) {
    // Asterisk-based roleplay without quotes:
    // *action* is atmosphere/action (italic, dim), outside is dialogue (bright, normal)
    tokenizeMarkdown(content, tokens, /* defaultToAction */ false);
  } else {
    // Plain chat without quotes or asterisks: entire message is dialogue
    tokens.push({ type: 'dialogue', text: content });
  }

  return (
    <Text style={[styles.defaultBase, style]} numberOfLines={numberOfLines}>
      {tokens.map((token, index) => {
        if (!token.text) return null;

        switch (token.type) {
          case 'dialogue':
            return (
              <Text
                key={index}
                style={[styles.dialogue, dialogueStyle]}
              >
                {token.text}
              </Text>
            );

          case 'action':
            return (
              <Text
                key={index}
                style={[styles.italic, styles.actionColor, actionStyle]}
              >
                {token.text}
              </Text>
            );

          case 'bold-action':
            return (
              <Text
                key={index}
                style={[
                  styles.bold,
                  styles.italic,
                  styles.actionColor,
                  boldStyle,
                  actionStyle,
                ]}
              >
                {token.text}
              </Text>
            );

          case 'bold':
            return (
              <Text key={index} style={[styles.bold, boldStyle]}>
                {token.text}
              </Text>
            );

          case 'code':
            return (
              <Text key={index} style={styles.inlineCode}>
                {token.text}
              </Text>
            );

          default:
            return <Text key={index}>{token.text}</Text>;
        }
      })}
    </Text>
  );
}

function tokenizeMarkdown(
  text: string,
  tokens: Array<{
    type: 'dialogue' | 'action' | 'bold' | 'bold-action' | 'code';
    text: string;
  }>,
  defaultToAction: boolean
) {
  const mdRegex = /(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_|`[^`]+`)/g;
  const parts = text.split(mdRegex);

  for (const part of parts) {
    if (!part) continue;

    if (part.startsWith('***') && part.endsWith('***') && part.length >= 6) {
      tokens.push({ type: 'bold-action', text: part.slice(3, -3) });
    } else if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      tokens.push({ type: 'bold', text: part.slice(2, -2) });
    } else if (
      (part.startsWith('*') && part.endsWith('*') && part.length >= 2) ||
      (part.startsWith('_') && part.endsWith('_') && part.length >= 2)
    ) {
      tokens.push({ type: 'action', text: part.slice(1, -1) });
    } else if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      tokens.push({ type: 'code', text: part.slice(1, -1) });
    } else {
      tokens.push({
        type: defaultToAction ? 'action' : 'dialogue',
        text: part,
      });
    }
  }
}

const styles = StyleSheet.create({
  defaultBase: {
    color: '#FFFFFF',
    fontSize: 15,
    lineHeight: 23,
  },
  dialogue: {
    color: '#FFFFFF',
    fontStyle: 'normal',
  },
  bold: {
    fontWeight: '700',
    color: '#FFFFFF',
  },
  italic: {
    fontStyle: 'italic',
  },
  actionColor: {
    color: '#9CA3AF',
  },
  inlineCode: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    backgroundColor: '#1E1E24',
    color: '#F43F5E',
    paddingHorizontal: 4,
    borderRadius: 4,
  },
});

