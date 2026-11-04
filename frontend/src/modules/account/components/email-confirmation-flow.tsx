import { Alert, Anchor, Center, Loader } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { failureMessage } from '@/common/api-client'
import { CenteredCard } from '@/common/centered-card'
import { useLinkToken } from '@/modules/password'
import { useSession } from '@/modules/session'

import { confirmEmailQueryOptions } from '../api/account'

/** Экран по ссылке из письма: подтверждает новый email, токен из `#token=…`. */
export function EmailConfirmationFlow() {
  const token = useLinkToken()
  const { subject, setSubject } = useSession()
  const query = useQuery({ ...confirmEmailQueryOptions(token ?? ''), enabled: token !== null })
  const result = query.data

  useEffect(() => {
    if (
      result?.kind === 'confirmed' &&
      subject?.type === 'manager' &&
      subject.id === result.managerId &&
      subject.email !== result.email
    ) {
      setSubject({ ...subject, email: result.email })
    }
  }, [result, subject, setSubject])

  const next = (
    <Anchor component={Link} to={subject ? '/' : '/login'}>
      {subject ? 'На главную' : 'Перейти ко входу'}
    </Anchor>
  )

  if (token && query.isPending) {
    return (
      <Center mih="60vh">
        <Loader aria-label="Подтверждаем email" />
      </Center>
    )
  }
  if (!token || result?.kind === 'expired') {
    return (
      <CenteredCard
        title="Ссылка устарела"
        description="Ссылка уже использована или срок её действия истёк. Измените email в профиле ещё раз."
      >
        {next}
      </CenteredCard>
    )
  }
  if (result?.kind === 'confirmed') {
    return (
      <CenteredCard
        title="Email подтверждён"
        description={`Теперь входите в Logos по адресу ${result.email}.`}
      >
        {next}
      </CenteredCard>
    )
  }
  return (
    <CenteredCard title="Не удалось подтвердить email">
      <Alert color="red" role="alert">
        {result?.kind === 'taken'
          ? 'Этот email уже занят другим сотрудником.'
          : failureMessage(result?.kind === 'failed' ? result.status : undefined)}
      </Alert>
      {next}
    </CenteredCard>
  )
}
