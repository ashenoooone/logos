import { createTheme, type MantineColorsTuple } from '@mantine/core'

const warm: MantineColorsTuple = [
  '#f7f6f3',
  '#efede8',
  '#e3e0da',
  '#d3cfc7',
  '#b8b3aa',
  '#928d84',
  '#2f3437',
  '#252a2c',
  '#1a1e20',
  '#111111',
]

export const appTheme = createTheme({
  fontFamily: 'system-ui, -apple-system, "Segoe UI", "Helvetica Neue", sans-serif',
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  primaryColor: 'warm',
  colors: { warm },
  defaultRadius: 'md',
  headings: {
    fontWeight: '600',
  },
})
