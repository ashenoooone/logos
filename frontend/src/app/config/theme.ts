import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Chip,
  Combobox,
  createTheme,
  darken,
  defaultVariantColorsResolver,
  Menu,
  Modal,
  Paper,
  parseThemeColor,
  PasswordInput,
  Popover,
  Textarea,
  TextInput,
  Title,
  Tooltip,
  type CSSVariablesResolver,
  type MantineColorsTuple,
  type VariantColorsResolver,
} from '@mantine/core'

/*
 * Визуальный язык по мотивам kontur.ru/career (замерено 2026-11-04):
 * текст #222, подложки #f6f6f6, ссылки #2270b8, счётчик уведомлений красный,
 * интерактив — пилюли, карточки и всплывающие окна — 16px, поля — 8px.
 * Отступления ради WCAG AA: второстепенный текст #6b6b6b (у них #858585, 3.7:1),
 * красный #e0302b (у них #f03b36, 3.9:1 с белым).
 */

// Почти чёрный — основной цвет: кнопки, выбранные пилюли, активные пункты.
const ink: MantineColorsTuple = [
  '#f6f6f6',
  '#ededed',
  '#dcdcdc',
  '#c4c4c4',
  '#9a9a9a',
  '#4a4a4a',
  '#222222',
  '#1a1a1a',
  '#121212',
  '#000000',
]

// Нейтральные. gray.0 — подложки, gray.3 — линии, gray.4 — рамка полей (3.5:1),
// gray.6 — `dimmed` (5.3:1 к белому).
const gray: MantineColorsTuple = [
  '#f6f6f6',
  '#efefef',
  '#e6e6e6',
  '#dcdcdc',
  '#8b8b8b',
  '#7d7d7d',
  '#6b6b6b',
  '#525252',
  '#3a3a3a',
  '#222222',
]

// Синий: blue.6 — ссылки (5.2:1), blue.0 — подложка исходящих и бейджей.
const blue: MantineColorsTuple = [
  '#e9f4ff',
  '#d3e8ff',
  '#a8d1ff',
  '#7bb8ff',
  '#54aaff',
  '#2291ff',
  '#2270b8',
  '#1d5f9c',
  '#184e80',
  '#123c63',
]

// Красный: red.6 — счётчик непрочитанных и ошибки (4.5:1 с белым).
const red: MantineColorsTuple = [
  '#fff0f0',
  '#ffdcdc',
  '#ffb8b7',
  '#ff8e8c',
  '#fe6866',
  '#fe4c4c',
  '#e0302b',
  '#c42722',
  '#a1201c',
  '#7d1915',
]

/*
 * Заметный hover: чёрная заливка светлеет до ink.5, белая кнопка сереет,
 * светлый вариант пишет оттенком 9, затемнённым до ≥4.5:1, и на hover берёт
 * плотную подложку оттенка 2.
 */
const variantColorResolver: VariantColorsResolver = (input) => {
  const colors = defaultVariantColorsResolver(input)
  const parsed = parseThemeColor({ color: input.color ?? input.theme.primaryColor, theme: input.theme })
  if (input.variant === 'white') {
    return { ...colors, hover: 'var(--mantine-color-gray-3)' }
  }
  if (!parsed.isThemeColor) {
    return colors
  }
  const shades = input.theme.colors[parsed.color]
  if (input.variant === 'filled' && parsed.color === 'ink') {
    return { ...colors, hover: shades[5] }
  }
  if (input.variant === 'light') {
    return { ...colors, color: darken(shades[9], 0.35), hover: shades[2], hoverColor: darken(shades[9], 0.45) }
  }
  return colors
}

// Вторичная кнопка — без заливки, чёрное кольцо 2px.
const outlined = (variant: string | undefined, prefix: 'button' | 'ai') =>
  variant === 'default'
    ? {
        root: {
          [`--${prefix}-bg`]: 'transparent',
          // На hover кольцо заливается: чёрная кнопка с белым текстом.
          [`--${prefix}-hover`]: 'var(--mantine-color-ink-6)',
          [`--${prefix}-hover-color`]: 'var(--mantine-color-white)',
          [`--${prefix}-bd`]: '2px solid var(--mantine-color-ink-6)',
          [`--${prefix}-color`]: 'var(--mantine-color-ink-6)',
        },
      }
    : { root: {} }

const SHADOW = '0 0 0 1px rgba(0, 0, 0, 0.05), 0 4px 20px rgba(33, 33, 42, 0.1)'

export const appTheme = createTheme({
  fontFamily: 'system-ui, -apple-system, "Segoe UI", "Helvetica Neue", sans-serif',
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  primaryColor: 'ink',
  primaryShade: 6,
  colors: { ink, gray, blue, red },
  black: '#222222',
  variantColorResolver,
  // Плотная сетка: меньше шаг и кегль, чем у Mantine по умолчанию.
  fontSizes: { xs: '12px', sm: '13px', md: '14px', lg: '16px', xl: '18px' },
  lineHeights: { xs: '1.5', sm: '1.5', md: '1.5', lg: '1.5', xl: '1.4' },
  spacing: { xs: '6px', sm: '8px', md: '12px', lg: '16px', xl: '24px' },
  // Карточки и окна — 16px (lg), поля ввода — 12px, кнопки, пилюли и бейджи — пилюля (xl).
  // md (8px) — мелочь вроде картинок и подсказок.
  radius: { xs: '4px', sm: '6px', md: '8px', lg: '16px', xl: '160px' },
  defaultRadius: 'md',
  shadows: { xs: SHADOW, sm: SHADOW, md: SHADOW, lg: SHADOW, xl: SHADOW },
  headings: {
    fontWeight: '600',
    sizes: {
      h1: { fontSize: '32px', lineHeight: '1.1', fontWeight: '600' },
      h2: { fontSize: '18px', lineHeight: '1.3', fontWeight: '500' },
      h3: { fontSize: '16px', lineHeight: '1.3', fontWeight: '500' },
    },
  },
  components: {
    ActionIcon: ActionIcon.extend({
      defaultProps: { radius: 'xl' },
      vars: (_, props) => outlined(props.variant, 'ai'),
    }),
    Alert: Alert.extend({ defaultProps: { radius: 'lg' } }),
    Anchor: Anchor.extend({ defaultProps: { c: 'blue.6' } }),
    Badge: Badge.extend({
      defaultProps: { radius: 'xl' },
      styles: { root: { textTransform: 'none', letterSpacing: 'normal', fontWeight: 500 } },
    }),
    Button: Button.extend({
      defaultProps: { radius: 'xl' },
      styles: { root: { fontWeight: 600 } },
      vars: (_, props) => outlined(props.variant, 'button'),
    }),
    // Пилюли фильтров: серые, выбранная — чёрная, без галочки.
    Chip: Chip.extend({
      defaultProps: { variant: 'filled', size: 'sm' },
      styles: { iconWrapper: { display: 'none' }, label: { paddingInline: 14 } },
    }),
    Combobox: Combobox.extend({ defaultProps: { radius: 'lg', shadow: 'md' } }),
    Menu: Menu.extend({ defaultProps: { radius: 'lg', shadow: 'md' } }),
    Modal: Modal.extend({
      defaultProps: { radius: 'lg', shadow: 'md' },
      styles: { title: { fontWeight: 600, fontSize: 'var(--mantine-font-size-xl)' } },
    }),
    Paper: Paper.extend({ defaultProps: { radius: 'lg' } }),
    PasswordInput: PasswordInput.extend({ defaultProps: { radius: '12px' } }),
    Popover: Popover.extend({ defaultProps: { radius: 'lg', shadow: 'md' } }),
    Textarea: Textarea.extend({ defaultProps: { radius: '12px' } }),
    TextInput: TextInput.extend({ defaultProps: { radius: '12px' } }),
    Title: Title.extend({ styles: { root: { letterSpacing: '-0.01em' } } }),
    Tooltip: Tooltip.extend({ defaultProps: { radius: 'md' } }),
  },
})

// Hover основного цвета Mantine берёт из глобальной переменной, мимо variantColorResolver.
export const cssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {},
  light: { '--mantine-primary-color-filled-hover': ink[5] },
  dark: { '--mantine-primary-color-filled-hover': ink[5] },
})
