export const theme = {
  fonts: {
    regular: 'ChangaOne-Regular',
    italic: 'ChangaOne-Italic',
    primary: 'ChangaOne-Regular',
  },
  colors: {
    background: '#000000',
    surface: '#0F0F11',
    surfaceElevated: '#18181B',
    border: '#27272A',
    borderFocus: '#52525B',
    text: '#FFFFFF',
    textSecondary: '#A1A1AA',
    textMuted: '#71717A',
    primary: '#FFFFFF',
    primaryText: '#000000',
    accent: '#3B82F6',
    error: '#EF4444',
    success: '#10B981',
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },
  radius: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    full: 9999,
  },
} as const;

export type Theme = typeof theme;
export type ThemeColors = typeof theme.colors;
