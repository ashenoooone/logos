import { Container } from '@mantine/core'

import { TagsAdminPanel } from '@/modules/tags'

export function TagCatalogPage() {
  return (
    <Container size="lg" py="xl" px="md">
      <TagsAdminPanel />
    </Container>
  )
}
