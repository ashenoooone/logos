import { Container } from '@mantine/core'

import { ManagersPanel } from '@/modules/managers'

export function EmployeesPage() {
  return (
    <Container size="lg" py="xl" px="md">
      <ManagersPanel />
    </Container>
  )
}
