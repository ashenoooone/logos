import { Container } from '@mantine/core'

import { AuditLogPanel } from '@/modules/audit'

export function AuditLogPage() {
  return (
    <Container size="xl" py="xl" px="md">
      <AuditLogPanel />
    </Container>
  )
}
