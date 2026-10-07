import { Message, Window } from '../components/Win98.tsx'

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
    <div className="screen screen-center">
      <div>
        <Window title="Wishly Setup" icon="wishly" className="dialog dialog-wide setup-screen">
          <div className="body">
            <Message icon="warn">
              <p>
                <b>Wishly needs local configuration.</b>
              </p>
              <p>
                The UI is built, but this workspace has no <code>frontend/.env</code> yet. Copy the
                example file to run the app locally.
              </p>
              <ol>
                <li>
                  <code>cp frontend/.env.example frontend/.env</code>
                </li>
                <li>
                  For local API calls, set <code>VITE_API_BASE_URL=http://localhost:8000/v1</code>
                </li>
                <li>
                  Run <code>npm run dev</code> in <code>frontend/</code>
                </li>
              </ol>
              <p>Missing right now:</p>
              <ul>
                {missing.map((item) => (
                  <li key={item.name}>
                    <b>{item.name}</b> — {item.hint}
                  </li>
                ))}
              </ul>
              <p className="field-hint">
                Or run without a backend:{' '}
                <code>VITE_MOCK_API=true VITE_DEV_NO_AUTH=true npm run dev</code>
              </p>
            </Message>
          </div>
        </Window>
      </div>
    </div>
  )
}
