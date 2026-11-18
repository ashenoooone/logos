import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiSend, type ApiResponse } from '@/common/api-client'

export const MAX_TEMPLATE_NAME = 100
export const MAX_TEMPLATE_TEXT = 4096

export interface Template {
  id: number
  name: string
  text: string
  own: boolean
  author: string | null
}

type TemplateList = { templates?: Template[] }

/** Шаблоны общие на компанию; `own` — создан текущим менеджером (#11). */
export const templatesQueryOptions = queryOptions({
  queryKey: ['templates'],
  queryFn: async ({ signal }) => apiGet<TemplateList>('/templates', signal),
  retry: false,
})

export function createTemplate(name: string, text: string): Promise<ApiResponse<TemplateList>> {
  return apiPost('/templates', { name, text })
}

export function updateTemplate(
  id: number,
  name: string,
  text: string,
): Promise<ApiResponse<TemplateList>> {
  return apiSend('PATCH', `/templates/${id}`, { name, text })
}

export function deleteTemplate(id: number): Promise<ApiResponse<TemplateList>> {
  return apiSend('DELETE', `/templates/${id}`)
}

// Переменные из обсуждения YouGile; в БД хранится исходный текст шаблона.
export const TEMPLATE_VARIABLES = ['клиент', 'номер', 'дата'] as const
export type TemplateVariable = (typeof TEMPLATE_VARIABLES)[number]

const VARIABLE_PATTERN = /\{(клиент|номер|дата)\}/g

/** Уникальные переменные шаблона в порядке появления. */
export function templateVariables(text: string): TemplateVariable[] {
  const found = [...text.matchAll(VARIABLE_PATTERN)].map((match) => match[1] as TemplateVariable)
  return [...new Set(found)]
}

export interface TemplatePart {
  text: string
  variable: TemplateVariable | null
  value: string
}

/** Текст шаблона частями: обычный текст и переменные с текущим значением. */
export function templateParts(text: string, values: Record<string, string>): TemplatePart[] {
  const parts: TemplatePart[] = []
  let last = 0
  for (const match of text.matchAll(VARIABLE_PATTERN)) {
    const index = match.index ?? 0
    if (index > last) {
      parts.push({ text: text.slice(last, index), variable: null, value: '' })
    }
    const variable = match[1] as TemplateVariable
    parts.push({ text: match[0], variable, value: values[variable]?.trim() ?? '' })
    last = index + match[0].length
  }
  if (last < text.length) {
    parts.push({ text: text.slice(last), variable: null, value: '' })
  }
  return parts
}

/** Подставляет заполненные переменные; незнакомые фигурные скобки не трогает. */
export function fillTemplate(text: string, values: Record<string, string>): string {
  return text.replace(VARIABLE_PATTERN, (placeholder, variable: TemplateVariable) => {
    const value = values[variable]?.trim()
    return value ? value : placeholder
  })
}
