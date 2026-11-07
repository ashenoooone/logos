import { TELEGRAM_LABEL } from '@/common/channel-label'
import { Anchor, Badge, Chip, CloseButton, Group, Stack, Text, Title } from '@mantine/core'
import type { ReactNode } from 'react'

import type { Tag } from '@/modules/tags'

import type { Filters, SavedFilter, Sort } from '../api/inbox'

const SORTS: { value: Sort; label: string }[] = [
  { value: 'newest', label: 'Новые сверху' },
  { value: 'oldest', label: 'Старые сверху' },
  { value: 'unread', label: 'Непрочитанные сверху' },
]

const CHANNELS = [{ value: 'telegram', label: TELEGRAM_LABEL }]

const STATUSES = [
  { value: 'unread', label: 'Есть непрочитанные' },
  { value: 'read', label: 'Всё прочитано' },
]

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Stack gap="xs" role="group" aria-label={label}>
      <Text fw={600}>{label}</Text>
      <Group gap={6}>{children}</Group>
    </Stack>
  )
}

/**
 * Колонка фильтров «Входящих» (#7): сортировка, фильтры пилюлями, сохранённые наборы,
 * число найденных. Пустой выбор в группе фильтра значит «любой».
 */
export function InboxToolbar({
  sort,
  onSort,
  filters,
  onFilters,
  tags,
  saved,
  found,
  onApplySaved,
  onSaveCurrent,
  onDeleteSaved,
}: {
  sort: Sort
  onSort: (sort: Sort) => void
  filters: Filters
  onFilters: (filters: Filters) => void
  tags: Tag[]
  saved: SavedFilter[]
  found: number
  onApplySaved: (filters: Filters) => void
  onSaveCurrent: (() => void) | null
  onDeleteSaved: (id: number) => void
}) {
  return (
    <Stack gap="lg">
      <Stack gap={2}>
        <Title order={1}>Входящие</Title>
        <Text size="sm" c="dimmed">
          найдено {found}
        </Text>
      </Stack>

      <Section label="Сортировка">
        <Chip.Group value={sort} onChange={(value) => onSort(value as Sort)}>
          {SORTS.map((item) => (
            <Chip key={item.value} value={item.value}>
              {item.label}
            </Chip>
          ))}
        </Chip.Group>
      </Section>

      <Section label="Канал">
        <Chip.Group
          multiple
          value={filters.channel}
          onChange={(value) => onFilters({ ...filters, channel: value as Filters['channel'] })}
        >
          {CHANNELS.map((item) => (
            <Chip key={item.value} value={item.value}>
              {item.label}
            </Chip>
          ))}
        </Chip.Group>
      </Section>

      <Section label="Статус">
        <Chip.Group
          multiple
          value={filters.status}
          onChange={(value) => onFilters({ ...filters, status: value as Filters['status'] })}
        >
          {STATUSES.map((item) => (
            <Chip key={item.value} value={item.value}>
              {item.label}
            </Chip>
          ))}
        </Chip.Group>
      </Section>

      <Section label="Теги">
        {tags.length === 0 && (
          <Text size="sm" c="dimmed">
            Тегов нет
          </Text>
        )}
        <Chip.Group
          multiple
          value={filters.tag.map(String)}
          onChange={(value) => onFilters({ ...filters, tag: value.map(Number) })}
        >
          {tags.map((tag) => (
            <Chip key={tag.id} value={String(tag.id)}>
              {tag.name}
            </Chip>
          ))}
        </Chip.Group>
      </Section>

      <Section label="Сохранённые">
        {saved.length === 0 && (
          <Text size="sm" c="dimmed">
            нет
          </Text>
        )}
        {saved.map((item) => (
          <Badge
            key={item.id}
            size="lg"
            variant="light"
            color="violet"
            style={{ cursor: 'pointer' }}
            onClick={() => onApplySaved(item.filters)}
            rightSection={
              <CloseButton
                size="xs"
                variant="transparent"
                aria-label={`Удалить набор ${item.name}`}
                onClick={(event) => {
                  event.stopPropagation()
                  onDeleteSaved(item.id)
                }}
              />
            }
          >
            {item.name}
          </Badge>
        ))}
        {onSaveCurrent && (
          <Anchor component="button" size="sm" onClick={onSaveCurrent}>
            сохранить текущие
          </Anchor>
        )}
      </Section>
    </Stack>
  )
}
