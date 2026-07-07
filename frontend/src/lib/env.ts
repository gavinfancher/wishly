/** Required Vite env vars for a working local/dev UI. */

export type EnvVar = {
  name: string
  hint: string
}

const REQUIRED_ENV: EnvVar[] = [
  {
    name: 'VITE_CLERK_PUBLISHABLE_KEY',
    hint: 'Clerk publishable key (pk_test_… or pk_live_…)',
  },
  {
    name: 'VITE_API_BASE_URL',
    hint: 'FastAPI base URL, e.g. http://localhost:8000',
  },
]

export function missingEnvVars(): EnvVar[] {
  // In the dev no-auth bypass there is no Clerk key to require; in mock mode
  // there is no backend to point at either.
  const devNoAuth = import.meta.env.VITE_DEV_NO_AUTH === 'true'
  const mockApi = import.meta.env.VITE_MOCK_API === 'true'
  return REQUIRED_ENV.filter((item) => {
    if (devNoAuth && item.name === 'VITE_CLERK_PUBLISHABLE_KEY') {
      return false
    }
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
