/** Required Vite env vars for a working local/dev UI. */

export type EnvVar = {
  name: string
  hint: string
}

const REQUIRED_ENV: EnvVar[] = [
  {
    name: 'VITE_API_BASE_URL',
    hint: 'API base URL including /v1, e.g. http://localhost:8000/v1',
  },
]

export function missingEnvVars(): EnvVar[] {
  // In mock mode there is no backend to point at.
  const mockApi = import.meta.env.VITE_MOCK_API === 'true'
  return REQUIRED_ENV.filter((item) => {
    if (mockApi && item.name === 'VITE_API_BASE_URL') {
      return false
    }
    const value = import.meta.env[item.name as keyof ImportMetaEnv]
    return typeof value !== 'string' || !value.trim() || value.includes('replace_me')
  })
}

export function getApiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL
  if (!base?.trim() || base.includes('replace_me')) {
    throw new Error('VITE_API_BASE_URL is not configured.')
  }
  return base
}
