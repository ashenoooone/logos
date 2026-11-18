import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Divider,
  Group,
  Modal,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Textarea,
  UnstyledButton,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { failureMessage, type ApiResponse } from '@/common/api-client'
import { useSession } from '@/modules/session'

import {
  createTemplate,
  deleteTemplate,
  fillTemplate,
  MAX_TEMPLATE_NAME,
  MAX_TEMPLATE_TEXT,
  templateParts,
  templateVariables,
  templatesQueryOptions,
  updateTemplate,
  type Template,
} from '../api/templates'

const fold = (value: string) => value.trim().toLocaleLowerCase('ru')

type TemplateList = { templates?: Template[] }

/**
 * «Шаблоны» в поле ответа (#11): поиск по названию и тексту, предпросмотр с
 * переменными, создание, изменение и удаление своих шаблонов. Вставка только
 * подставляет текст в поле ввода — отправляет менеджер обычным способом.
 */
export function ReplyTemplates({
  conversationName,
  onInsert,
}: {
  conversationName: string
  onInsert: (text: string) => void
}) {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const query = useQuery(templatesQueryOptions)
  const [opened, setOpened] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [form, setForm] = useState<{ id: number | null; name: string; text: string } | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const all = query.data?.status === 200 ? (query.data.data.templates ?? []) : []
  const found = all.filter((template) => {
    const needle = fold(search)
    return !needle || fold(template.name).includes(needle) || fold(template.text).includes(needle)
  })
  const selected = all.find((template) => template.id === selectedId) ?? null
  const variables = selected ? templateVariables(selected.text) : []
  const missing = variables.some((variable) => !values[variable]?.trim())

  function reset() {
    setSearch('')
    setSelectedId(null)
    setValues({})
    setForm(null)
    setError(null)
  }

  function openDialog() {
    reset()
    setOpened(true)
    void query.refetch()
  }

  function select(template: Template) {
    setSelectedId(template.id)
    setValues(
      templateVariables(template.text).includes('клиент') ? { клиент: conversationName } : {},
    )
  }

  function startCreate(withName = '') {
    setError(null)
    setForm({ id: null, name: withName.slice(0, MAX_TEMPLATE_NAME), text: '' })
  }

  function startEdit(template: Template) {
    setError(null)
    setForm({ id: template.id, name: template.name, text: template.text })
  }

  async function run(action: () => Promise<ApiResponse<TemplateList>>) {
    setPending(true)
    setError(null)
    try {
      const response = await action()
      if (response.status === 401) {
        setSubject(null)
      } else if (response.status === 403) {
        setError('Изменять и удалять можно только свои шаблоны.')
      } else if (response.status !== 200) {
        setError(failureMessage(response.status))
      } else {
        queryClient.setQueryData(templatesQueryOptions.queryKey, response)
        setSelectedId(null)
        setValues({})
        setForm(null)
      }
    } catch {
      setError(failureMessage())
    }
    setPending(false)
  }

  function save() {
    if (!form) return
    void run(() =>
      form.id === null
        ? createTemplate(form.name, form.text)
        : updateTemplate(form.id, form.name, form.text),
    )
  }

  function remove(template: Template) {
    if (window.confirm(`Удалить шаблон «${template.name}»? Уже отправленные сообщения не изменятся.`)) {
      void run(() => deleteTemplate(template.id))
    }
  }

  return (
    <>
      <Button variant="default" size="lg" onClick={openDialog}>
        Шаблоны
      </Button>
      <Modal opened={opened} onClose={() => setOpened(false)} title="Шаблоны ответов" size="lg">
        <Stack gap="sm">
          {error && (
            <Alert color="red" role="alert" withCloseButton onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
          {form ? (
            <Stack gap="sm">
              <TextInput
                aria-label="Название шаблона"
                label="Название"
                maxLength={MAX_TEMPLATE_NAME}
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.currentTarget.value })}
              />
              <Textarea
                aria-label="Текст шаблона"
                label="Текст"
                autosize
                minRows={4}
                maxRows={10}
                maxLength={MAX_TEMPLATE_TEXT}
                value={form.text}
                onChange={(event) => setForm({ ...form, text: event.currentTarget.value })}
              />
              <Text size="xs" c="dimmed">
                Переменные: {'{клиент}'}, {'{номер}'}, {'{дата}'}. Менеджер заполнит их в
                предпросмотре перед вставкой.
              </Text>
              <Group justify="flex-end" gap="xs">
                <Button variant="default" onClick={() => setForm(null)}>
                  Отмена
                </Button>
                <Button
                  loading={pending}
                  disabled={!form.name.trim() || !form.text.trim()}
                  onClick={save}
                >
                  Сохранить
                </Button>
              </Group>
            </Stack>
          ) : (
            <>
              <Group gap="xs" wrap="nowrap">
                <TextInput
                  aria-label="Поиск шаблонов"
                  placeholder="Поиск по названию и тексту"
                  style={{ flex: 1 }}
                  value={search}
                  onChange={(event) => setSearch(event.currentTarget.value)}
                />
                <Button variant="light" onClick={() => startCreate(search)}>
                  Создать шаблон
                </Button>
              </Group>
              {query.isPending ? (
                <Text size="sm" c="dimmed">
                  Загрузка шаблонов…
                </Text>
              ) : found.length === 0 ? (
                <Stack gap="xs" align="flex-start">
                  <Text size="sm">{all.length === 0 ? 'Пока нет шаблонов.' : 'Ничего не найдено.'}</Text>
                  <Text size="sm" c="dimmed">
                    {all.length === 0
                      ? 'Создайте шаблон, чтобы вставлять готовый текст в ответ.'
                      : 'Измените запрос или создайте новый шаблон с этим названием.'}
                  </Text>
                  <Button size="xs" onClick={() => startCreate(search)}>
                    Создать шаблон
                  </Button>
                </Stack>
              ) : (
                <ScrollArea.Autosize mah={320}>
                  <Stack gap={0}>
                    {found.map((template) => (
                      <Group
                        key={template.id}
                        gap="xs"
                        wrap="nowrap"
                        py={6}
                        style={{ borderBottom: '1px solid var(--mantine-color-gray-2)' }}
                      >
                        <UnstyledButton style={{ flex: 1, minWidth: 0 }} onClick={() => select(template)}>
                          <Group gap={6} wrap="nowrap">
                            <Text size="sm" fw={selectedId === template.id ? 600 : 400} truncate>
                              {template.name}
                            </Text>
                            {template.own && (
                              <Badge size="xs" variant="light" color="gray">
                                мой
                              </Badge>
                            )}
                          </Group>
                          <Text size="xs" c="dimmed" truncate>
                            {template.text}
                          </Text>
                        </UnstyledButton>
                        {template.own && (
                          <>
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              aria-label={`Редактировать шаблон ${template.name}`}
                              onClick={() => startEdit(template)}
                            >
                              ✎
                            </ActionIcon>
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="red"
                              aria-label={`Удалить шаблон ${template.name}`}
                              onClick={() => remove(template)}
                            >
                              ×
                            </ActionIcon>
                          </>
                        )}
                      </Group>
                    ))}
                  </Stack>
                </ScrollArea.Autosize>
              )}
              {selected && (
                <>
                  <Divider label="Предпросмотр" labelPosition="left" />
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                    {templateParts(selected.text, values).map((part, index) =>
                      part.variable && !part.value ? (
                        <Text key={index} span c="red" fw={600} bg="red.0">
                          {part.text}
                        </Text>
                      ) : (
                        <Text key={index} span>
                          {part.variable ? part.value : part.text}
                        </Text>
                      ),
                    )}
                  </Text>
                  {variables.length > 0 && (
                    <Stack gap="xs">
                      {variables.map((variable) => (
                        <TextInput
                          key={variable}
                          label={`{${variable}}`}
                          size="xs"
                          error={!values[variable]?.trim() ? 'Заполните переменную' : null}
                          value={values[variable] ?? ''}
                          onChange={(event) =>
                            setValues((current) => ({
                              ...current,
                              [variable]: event.currentTarget.value,
                            }))
                          }
                        />
                      ))}
                    </Stack>
                  )}
                  <Group justify="flex-end">
                    <Button
                      disabled={missing}
                      onClick={() => {
                        onInsert(fillTemplate(selected.text, values))
                        setOpened(false)
                      }}
                    >
                      Вставить в ответ
                    </Button>
                  </Group>
                </>
              )}
            </>
          )}
        </Stack>
      </Modal>
    </>
  )
}
