import {
  Alert,
  Button,
  Group,
  Loader,
  Menu,
  Paper,
  ScrollArea,
  Stack,
  Text,
  Textarea,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'

import { failureMessage } from '@/common/api-client'
import { useSession } from '@/modules/session'

import {
  addComment,
  commentsQueryOptions,
  MAX_TEXT_LENGTH,
  type CommentMention,
  type InternalComment,
  type Result,
} from '../api/inbox'

/**
 * «Команда» (#15): внутренний тред диалога. Комментарии не уходят клиенту,
 * не влияют на непрочитанность и показываются с жёлтой подсветкой.
 * `active` включает опрос только на открытой вкладке; черновик живёт в своём
 * состоянии и не теряется при переключении «Клиент / Команда».
 */
export function ThreadComments({ id, active }: { id: number; active: boolean }) {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const query = useQuery({ ...commentsQueryOptions(id), enabled: active })
  const viewport = useRef<HTMLDivElement>(null)
  const [text, setText] = useState('')
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const data = query.data
  const thread = data?.kind === 'success' ? data.value : null
  const count = thread?.comments.length ?? 0

  useEffect(() => {
    if (data?.kind === 'unauthorized') {
      setSubject(null)
    }
  }, [data, setSubject])

  useEffect(() => {
    viewport.current?.scrollTo({ top: viewport.current.scrollHeight })
  }, [count])

  function mention(name: string) {
    setText((current) => `${current}${current && !current.endsWith(' ') ? ' ' : ''}@${name} `)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const body = text.trim()
    if (!body || pending) {
      return
    }
    setPending(true)
    setNotice(null)
    try {
      const result: Result<InternalComment> = await addComment(id, body)
      if (result.kind === 'success') {
        setText('')
        await queryClient.invalidateQueries({ queryKey: commentsQueryOptions(id).queryKey })
      } else if (result.kind === 'unauthorized') {
        setSubject(null)
      } else {
        setNotice(result.kind === 'not-found' ? 'Диалог не найден.' : failureMessage(result.status))
      }
    } catch {
      setNotice(failureMessage())
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <ScrollArea style={{ flex: 1 }} viewportRef={viewport} px="md" bg="yellow.0">
        <Stack gap="sm" py="md">
          {query.isPending && active && <Loader m="auto" aria-label="Загрузка комментариев" />}
          {!query.isPending && data?.kind === 'failed' && (
            <Alert color="red" role="alert" title="Не удалось загрузить комментарии">
              <Group gap="xs">
                <Text size="sm">{failureMessage(data.status)}</Text>
                <Button size="xs" variant="light" onClick={() => void query.refetch()}>
                  Повторить
                </Button>
              </Group>
            </Alert>
          )}
          {thread && thread.comments.length === 0 && (
            <Text size="sm" c="dimmed">
              Комментариев пока нет. Напишите команде и упомяните коллегу через @.
            </Text>
          )}
          {thread?.comments.map((comment) => (
            <CommentBubble key={comment.id} comment={comment} />
          ))}
        </Stack>
      </ScrollArea>

      {notice && (
        <Alert color="red" role="alert" mx="md" mb="xs" withCloseButton onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <Stack gap={6} p="md" bg="yellow.0" style={{ borderTop: '1px solid var(--mantine-color-yellow-3)' }}>
          <Group justify="space-between" gap="xs">
            <Text size="xs" c="dimmed">
              Видят только сотрудники — клиенту не отправляется
            </Text>
            <Menu position="top-end" withinPortal>
              <Menu.Target>
                <Button type="button" size="compact-xs" variant="default" disabled={!thread?.colleagues.length}>
                  Упомянуть
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                {(thread?.colleagues ?? []).map((colleague) => (
                  <Menu.Item key={colleague.id} onClick={() => mention(colleague.name)}>
                    {colleague.name}
                  </Menu.Item>
                ))}
              </Menu.Dropdown>
            </Menu>
          </Group>
          <Textarea
            aria-label="Комментарий команде"
            placeholder="Комментарий для команды…"
            autosize
            minRows={1}
            maxRows={6}
            bg="white"
            maxLength={MAX_TEXT_LENGTH}
            value={text}
            onChange={(event) => setText(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                void handleSubmit(event)
              }
            }}
          />
          <Group justify="flex-end">
            <Button type="submit" size="xs" color="yellow" c="dark" loading={pending} disabled={!text.trim()}>
              Отправить
            </Button>
          </Group>
        </Stack>
      </form>
    </>
  )
}

function CommentBubble({ comment }: { comment: InternalComment }) {
  return (
    <Paper
      px="md"
      py="sm"
      maw="85%"
      bg="yellow.1"
      style={{
        alignSelf: 'flex-start',
        border: '1px solid var(--mantine-color-yellow-3)',
        borderRadius: '12px 12px 12px 4px',
      }}
    >
      <Stack gap={4}>
        <Text size="xs" c="dimmed">
          {comment.author ?? 'Менеджер'} · {commentDate(comment.created_at)}
        </Text>
        <Text size="sm" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
          <CommentText text={comment.text} mentions={comment.mentions} />
        </Text>
      </Stack>
    </Paper>
  )
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Текст с подсветкой @упоминаний; удалённый коллега помечается явно. */
function CommentText({ text, mentions }: { text: string; mentions: CommentMention[] }) {
  if (mentions.length === 0) {
    return <>{text}</>
  }
  const pattern = new RegExp(`@(?:${mentions.map((item) => escapeRegExp(item.name)).join('|')})`, 'g')
  const nodes: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(pattern)) {
    const at = match.index ?? 0
    if (at > last) {
      nodes.push(text.slice(last, at))
    }
    const token = match[0]
    const mention = mentions.find((item) => `@${item.name}` === token)
    nodes.push(
      <Text key={`mention-${at}`} span bg="yellow.3" px={4} style={{ borderRadius: 4 }}>
        {token}
      </Text>,
    )
    if (mention && !mention.available) {
      nodes.push(
        <Text key={`missing-${at}`} span c="dimmed">
          {' (пользователь не найден)'}
        </Text>,
      )
    }
    last = at + token.length
  }
  if (last < text.length) {
    nodes.push(text.slice(last))
  }
  return <>{nodes}</>
}

function commentDate(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
