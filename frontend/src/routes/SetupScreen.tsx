type MissingVar = {
  name: string
  hint: string
}

type SetupScreenProps = {
  missing: MissingVar[]
}

/**
 * Shown when required Vite env vars are absent — avoids a blank page on first clone.
 */
export default function SetupScreen({ missing }: SetupScreenProps) {
  return (
    <div className="setup-screen">
      <h1>Wishly needs local configuration</h1>
      <p>
        The UI is built, but this workspace has no <code>frontend/.env</code> yet. Copy the example
        file and add your Clerk key to run the app locally.
      </p>

      <ol className="setup-steps">
        <li>
          <code>cp frontend/.env.example frontend/.env</code>
        </li>
        <li>
          Set <code>VITE_CLERK_PUBLISHABLE_KEY</code> from the Clerk dashboard (API Keys)
        </li>
        <li>
          For local API calls, set <code>VITE_API_BASE_URL=http://localhost:8000</code>
        </li>
        <li>
          Run <code>just web-dev</code> (or <code>npm run dev</code> in <code>frontend/</code>)
        </li>
      </ol>

      <p className="setup-missing">Missing right now:</p>
      <ul>
        {missing.map((item) => (
          <li key={item.name}>
            <strong>{item.name}</strong> — {item.hint}
          </li>
        ))}
      </ul>

      <p className="text-muted">
        After sign-in you&apos;ll see onboarding, then the events UI. Nothing is deployed to
        wishly.dev yet — that&apos;s T7.4 in the plan.
      </p>
    </div>
  )
}
