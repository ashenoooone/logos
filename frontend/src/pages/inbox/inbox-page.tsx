import { Container } from '@mantine/core'

import { InboxPanel } from '@/modules/inbox'

export function InboxPage() {
  return (
    <Container size="xl" py="lg" px="md">
      <InboxPanel />
    </Container>
  )
}
