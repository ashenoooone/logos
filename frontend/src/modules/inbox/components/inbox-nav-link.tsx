import { Badge } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'

import { useSession } from '@/modules/session'

import { conversationsQueryOptions } from '../api/inbox'

const TITLE = 'Logos'

let audio: AudioContext | null = null

/** Короткий сигнал без звукового файла; без звука (политика autoplay) остаётся счётчик. */
function beep() {
  try {
    audio ??= new AudioContext()
    void audio.resume()
    const oscillator = audio.createOscillator()
    const gain = audio.createGain()
    oscillator.frequency.value = 880
    gain.gain.value = 0.1
    oscillator.connect(gain).connect(audio.destination)
    oscillator.start()
    oscillator.stop(audio.currentTime + 0.15)
  } catch {
    // AudioContext недоступен
  }
}

/**
 * Пункт меню «Входящие» с общим числом непрочитанных. Пока менеджер в приложении,
 * показывает счётчик на вкладке браузера и подаёт звук на новое входящее сообщение.
 */
export function InboxNavLink() {
  const { setSubject } = useSession()
  const { data } = useQuery(conversationsQueryOptions())
  const list = data?.kind === 'success' ? data.value : null
  const total = list?.unread_total ?? 0
  const lastIncoming = list?.last_incoming_id
  const seen = useRef<number | null | undefined>(undefined)

  useEffect(() => {
    if (data?.kind === 'unauthorized') {
      setSubject(null)
    }
  }, [data, setSubject])

  useEffect(() => {
    document.title = total > 0 ? `(${total}) ${TITLE}` : TITLE
  }, [total])
  useEffect(() => () => void (document.title = TITLE), [])

  useEffect(() => {
    if (lastIncoming === undefined) {
      return
    }
    // Первый ответ только запоминается: звук — на сообщения, пришедшие после входа.
    if (seen.current !== undefined && (lastIncoming ?? 0) > (seen.current ?? 0)) {
      beep()
    }
    seen.current = lastIncoming
  }, [lastIncoming])

  return (
    <Link to="/inbox" className="logos-nav">
      Входящие
      {total > 0 && (
        <Badge size="sm" color="red" circle={total < 10} aria-label={`непрочитанных: ${total}`}>
          {total}
        </Badge>
      )}
    </Link>
  )
}
