import { Anchor, Badge, CloseButton, Group, MultiSelect, Select, Text } from '@mantine/core'

import type { Tag } from '@/modules/tags'

import type { Filters, SavedFilter, Sort } from '../api/inbox'

const SORTS: { value: Sort; label: string }[] = [
  { value: 'newest', label: 'Новые сверху' },
  { value: 'oldest', label: 'Старые сверху' },
  { value: 'unread', label: 'Непрочитанные сверху' },
]

const CHANNELS = [{ value: 'telegram', label: 'Telegram' }]

const STATUSES = [
  { value: 'unread', label: 'Есть непрочитанные' },
  { value: 'read', label: 'Всё прочитано' },
]

/** Панель «Входящих» (#7): сортировка, фильтры, сохранённые наборы, число найденных. */
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
  const filterProps = { size: 'xs', clearable: true, w: 200, comboboxProps: { width: 240 } } as const
  return (
    <>
      <Group gap="sm" wrap="wrap" align="center">
        <Text size="sm">Сортировка:</Text>
        <Select
          aria-label="Сортировка"
          size="xs"
          w={200}
          allowDeselect={false}
          data={SORTS}
          value={sort}
          onChange={(value) => value && onSort(value as Sort)}
        />
        <Text size="sm">Фильтры:</Text>
        <MultiSelect
          {...filterProps}
          aria-label="Канал"
          placeholder={filters.channel.length ? undefined : 'Канал'}
          data={CHANNELS}
          value={filters.channel}
          onChange={(value) => onFilters({ ...filters, channel: value as Filters['channel'] })}
        />
        <MultiSelect
          {...filterProps}
          aria-label="Статус"
          placeholder={filters.status.length ? undefined : 'Статус'}
          data={STATUSES}
          value={filters.status}
          onChange={(value) => onFilters({ ...filters, status: value as Filters['status'] })}
        />
        <MultiSelect
          {...filterProps}
          aria-label="Тег"
          placeholder={filters.tag.length ? undefined : 'Тег'}
          searchable
          nothingFoundMessage="Тегов нет"
          data={tags.map((tag) => ({ value: String(tag.id), label: tag.name }))}
          value={filters.tag.map(String)}
          onChange={(value) => onFilters({ ...filters, tag: value.map(Number) })}
        />
      </Group>
      <Group gap={6} wrap="wrap">
        <Text size="sm">★ Сохранённые:</Text>
        {saved.length === 0 && (
          <Text size="sm" c="dimmed">
            нет
          </Text>
        )}
        {saved.map((item) => (
          <Badge
            key={item.id}
            variant="light"
            color="violet"
            tt="none"
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
            · сохранить текущие
          </Anchor>
        )}
        <Text size="sm" c="dimmed">
          · найдено {found}
        </Text>
      </Group>
    </>
  )
}
