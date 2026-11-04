import { CenteredCard } from '@/common/centered-card'
import { ForgotPasswordForm } from '@/modules/password'

export function ForgotPasswordPage() {
  return (
    <CenteredCard
      title="Восстановление пароля"
      description="Укажите email, с которым вы входите в Logos. Мы отправим ссылку для нового пароля."
    >
      <ForgotPasswordForm />
    </CenteredCard>
  )
}
