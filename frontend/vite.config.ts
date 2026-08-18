import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Local-only escape hatches. Each ships a build that is wrong in production:
 * `VITE_DEV_NO_AUTH` skips Clerk entirely (anyone is signed in as a fixed user)
 * and `VITE_MOCK_API` serves fixture data instead of the real API. A production
 * build that inherited either from a stray .env would look fine and be broken,
 * so fail the build instead of shipping it.
 */
const DEV_ONLY_FLAGS = ['VITE_DEV_NO_AUTH', 'VITE_MOCK_API'] as const

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  if (mode === 'production') {
    const enabled = DEV_ONLY_FLAGS.filter((flag) => env[flag] === 'true')
    if (enabled.length > 0) {
      throw new Error(
        `Refusing to build for production with ${enabled.join(' and ')} set to true. ` +
          `These are local-development only. Set them to false in the build environment.`
      )
    }
    if (!env.VITE_CLERK_PUBLISHABLE_KEY || env.VITE_CLERK_PUBLISHABLE_KEY.includes('replace_me')) {
      throw new Error(
        'Refusing to build for production without a real VITE_CLERK_PUBLISHABLE_KEY.'
      )
    }
  }

  return { plugins: [react()] }
})
