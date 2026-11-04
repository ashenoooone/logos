import { Container } from '@mantine/core'

import { ProfilePanel } from '@/modules/account'

export function ProfilePage() {
  return (
    <Container size={560} py="xl" px="md">
      <ProfilePanel />
    </Container>
  )
}
