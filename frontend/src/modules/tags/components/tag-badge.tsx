import { Badge, CloseButton } from '@mantine/core'

import { tagColor, type TagRef } from '../api/tags'

/** Тег диалога; с `onRemove` — с крестиком «снять». */
export function TagBadge({ tag, onRemove }: { tag: TagRef; onRemove?: () => void }) {
  return (
    <Badge
      variant="light"
      color={tagColor(tag.id)}
      tt="none"
      rightSection={
        onRemove && (
          <CloseButton size="xs" variant="transparent" aria-label={`Снять тег ${tag.name}`} onClick={onRemove} />
        )
      }
    >
      {tag.name}
    </Badge>
  )
}
