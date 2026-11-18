export const TELEGRAM_LABEL = 'Telegram'

/** Название канала для метки обращения; пока известен только Telegram. */
export function channelLabel(channel: string): string {
  return channel === 'telegram' ? TELEGRAM_LABEL : channel
}
