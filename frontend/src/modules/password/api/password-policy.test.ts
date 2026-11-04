import { describe, expect, it } from 'vitest'

import { passwordRules } from './password-policy'

const failed = (password: string, confirmation = password) =>
  passwordRules(password, confirmation)
    .filter((rule) => !rule.ok)
    .map((rule) => rule.label)

describe('passwordRules', () => {
  it('принимает 8 символов с буквой и цифрой при совпадающем повторе', () => {
    expect(failed('abcdefg1')).toEqual([])
  })

  it('называет каждое невыполненное требование', () => {
    expect(failed('abc1')).toEqual(['Минимум 8 символов'])
    expect(failed('12345678')).toEqual(['Хотя бы одна буква'])
    expect(failed('abcdefgh')).toEqual(['Хотя бы одна цифра'])
    expect(failed('abcdefg1', 'abcdefg2')).toEqual(['Пароли совпадают'])
    expect(failed('', '')).toEqual([
      'Минимум 8 символов',
      'Хотя бы одна буква',
      'Хотя бы одна цифра',
      'Пароли совпадают',
    ])
  })

  it('считает буквой любой алфавит, а длину — в символах, не в UTF-16', () => {
    expect(failed('пароль12')).toEqual([])
    expect(failed('😀😀😀a1')).toEqual(['Минимум 8 символов'])
  })

  it('не обрезает пробелы: повтор должен совпасть точно', () => {
    expect(failed('abcdefg1 ', 'abcdefg1')).toEqual(['Пароли совпадают'])
  })
})
