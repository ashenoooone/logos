// Повторяет серверную политику (security.py): длина в кодовых точках, буква — любая
// Unicode-буква (str.isalpha), цифра — десятичная (str.isdecimal). Сервер остаётся проверкой истины.

export interface PasswordRule {
  label: string
  ok: boolean
}

export function passwordRules(password: string, confirmation: string): PasswordRule[] {
  return [
    { label: 'Минимум 8 символов', ok: [...password].length >= 8 },
    { label: 'Хотя бы одна буква', ok: /\p{L}/u.test(password) },
    { label: 'Хотя бы одна цифра', ok: /\p{Nd}/u.test(password) },
    { label: 'Пароли совпадают', ok: confirmation !== '' && password === confirmation },
  ]
}
