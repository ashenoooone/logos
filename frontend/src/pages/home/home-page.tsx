import { TELEGRAM_LABEL } from '@/common/channel-label'
import { Container, Stack, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { channelQueryOptions } from '@/modules/channels'
import { conversationsQueryOptions } from '@/modules/inbox'
import { managersQueryOptions } from '@/modules/managers'
import { useSession } from '@/modules/session'
import { adminTagsQueryOptions } from '@/modules/tags'

/** Главная — разводящая: бенто из плиток разделов роли с живыми числами. */
export function HomePage() {
  const { subject } = useSession()

  return (
    <Container size="xl" py={{ base: 'xl', sm: 48 }} px="md">
      <Stack gap="xl">
        <Stack gap="xs">
          <Title order={1} fz={{ base: 32, sm: 48 }} fw={500} lh={1.05} style={{ letterSpacing: '-0.02em' }}>
            {subject?.type === 'manager' ? `Здравствуйте, ${subject.name.split(' ')[0]}` : 'Панель администратора'}
          </Title>
          <Text c="dimmed" fz="lg">
            {subject?.type === 'manager' ? 'Что ждёт ответа и куда перейти.' : 'Команда, канал и теги компании.'}
          </Text>
        </Stack>

        {subject?.type === 'manager' ? <ManagerTiles /> : <AdminTiles />}
      </Stack>
    </Container>
  )
}

function AdminTiles() {
  const managers = useQuery(managersQueryOptions).data
  const channel = useQuery(channelQueryOptions).data
  const tagsResponse = useQuery(adminTagsQueryOptions).data

  const team = managers?.kind === 'success' ? managers.managers : null
  const pending = team?.filter((manager) => manager.status === 'pending').length ?? 0
  const ch = channel?.kind === 'success' ? channel.value : null
  const tags = tagsResponse?.status === 200 ? (tagsResponse.data?.tags ?? null) : null
  const marks = tags?.reduce((sum, tag) => sum + tag.conversation_count, 0) ?? 0

  return (
    <div className="logos-bento">
      <HubTile to="/employees" tone="violet" title="Сотрудники" tall>
        <Figure
          value={team?.length}
          unit={team ? plural(team.length, 'менеджер', 'менеджера', 'менеджеров') : ''}
        />
        {team && (
          <Pills>
            <span>{team.length - pending} активны</span>
            {pending > 0 && <span>{pending} ждут пароль</span>}
          </Pills>
        )}
      </HubTile>

      <HubTile to="/channels" tone={ch?.status === 'connected' ? 'green' : 'night'} title={`Канал ${TELEGRAM_LABEL}`}>
        <Text className="logos-hub-value-sm">{ch?.bot_username ? `@${ch.bot_username}` : 'Бот не подключён'}</Text>
        {ch && (
          <Pills>
            <span>{CHANNEL_STATUS[ch.status]}</span>
          </Pills>
        )}
      </HubTile>

      <HubTile to="/tag-catalog" tone="orange" title="Теги">
        <Figure value={tags?.length} unit={tags ? plural(tags.length, 'тег', 'тега', 'тегов') : ''} />
        {tags && (
          <Pills>
            <span>{tags.filter((tag) => tag.standard).length} стандартных</span>
            <span>{marks} на диалогах</span>
          </Pills>
        )}
      </HubTile>
    </div>
  )
}

function ManagerTiles() {
  const data = useQuery(conversationsQueryOptions()).data
  const list = data?.kind === 'success' ? data.value : null
  const waiting = list?.conversations.filter((item) => item.unread_count > 0).length
  const failed = list?.conversations.filter((item) => item.last_message?.status === 'failed').length ?? 0

  return (
    <div className="logos-bento">
      <HubTile to="/inbox" tone="violet" title="Входящие" tall>
        <Figure
          value={list?.unread_total}
          unit={list ? plural(list.unread_total, 'непрочитанное', 'непрочитанных', 'непрочитанных') : ''}
        />
        {list && (
          <Pills>
            <span>{list.conversations.length} диалогов</span>
            {failed > 0 && <span>{failed} не доставлено</span>}
          </Pills>
        )}
      </HubTile>

      <HubTile to="/inbox" tone="green" title="Ждут ответа">
        <Figure
          value={waiting}
          unit={waiting === undefined ? '' : plural(waiting, 'диалог', 'диалога', 'диалогов')}
        />
      </HubTile>

      <HubTile to="/profile" tone="orange" title="Профиль">
        <Text className="logos-hub-value-sm">Имя, почта, пароль</Text>
      </HubTile>
    </div>
  )
}

const CHANNEL_STATUS = { connected: 'Подключён', error: 'Ошибка подключения', disconnected: 'Отключён' } as const

/** Русское склонение по числу: 1 тег, 2 тега, 5 тегов. */
function plural(n: number, one: string, few: string, many: string) {
  const d10 = n % 10
  const d100 = n % 100
  if (d10 === 1 && d100 !== 11) return one
  if (d10 >= 2 && d10 <= 4 && (d100 < 12 || d100 > 14)) return few
  return many
}

type TileProps = {
  to: '/employees' | '/channels' | '/tag-catalog' | '/inbox' | '/profile'
  tone: 'violet' | 'green' | 'orange' | 'night'
  title: string
  tall?: boolean
  children: ReactNode
}

/** Плитка-ссылка: название сверху, стрелка-кружок справа, содержимое прижато книзу. */
function HubTile({ to, tone, title, tall, children }: TileProps) {
  return (
    <Link to={to} className={`logos-hub-tile logos-hub-${tone}${tall ? ' logos-hub-tall' : ''}`}>
      <div className="logos-hub-head">
        <Text component="span" className="logos-hub-title">
          {title}
        </Text>
        <span className="logos-hub-arrow" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M6 14 14 6M7 6h7v7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </span>
      </div>
      <div className="logos-hub-body">{children}</div>
    </Link>
  )
}

/** Крупное число и подпись к нему на одной базовой линии. */
function Figure({ value, unit }: { value: number | undefined; unit: string }) {
  return (
    <p className="logos-hub-figure">
      <span className="logos-hub-number">{value ?? '—'}</span> {unit}
    </p>
  )
}

function Pills({ children }: { children: ReactNode }) {
  return <div className="logos-hub-pills">{children}</div>
}
