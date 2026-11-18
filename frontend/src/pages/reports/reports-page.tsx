import { Container } from '@mantine/core'

import { ReportsPanel } from '@/modules/reports'

export function ReportsPage() {
  return (
    <Container size="xl" py="xl" px="md">
      <ReportsPanel />
    </Container>
  )
}
