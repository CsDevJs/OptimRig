/** Hover colours for small elements, cycled by position so neighbours differ. */
export const HOVER_COLORS = ['hov-green', 'hov-blue', 'hov-purple', 'hov-gold', 'hov-teal'] as const
export const HOVER_HEX: Record<(typeof HOVER_COLORS)[number], string> = {
  'hov-green': '#34c37f',
  'hov-blue': '#7797ff',
  'hov-purple': '#a78bfa',
  'hov-gold': '#e2b74a',
  'hov-teal': '#38c7d6',
}
export const hov = (index: number) => `hov ${HOVER_COLORS[index % HOVER_COLORS.length]}`
