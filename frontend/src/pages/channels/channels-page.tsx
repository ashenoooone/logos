import { Container } from '@mantine/core'

import { ChannelsPanel } from '@/modules/channels'

export function ChannelsPage() {
  return (
    <Container size="lg" py="xl" px="md">
      <ChannelsPanel />
    </Container>
  )
}
