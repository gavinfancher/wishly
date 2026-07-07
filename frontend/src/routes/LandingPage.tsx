import { Link } from 'react-router-dom'

import { useWishlyAuth } from '../lib/auth-context.ts'
import { monthAbbr } from '../lib/dates.ts'

/**
 * Public marketing page at `/`.
 *
 * The signature visual is the red pen circle — the mark you'd draw around a
 * date on a wall calendar — around the word "circle" in the headline, echoed
 * by the reminder-email mock in the hero.
 */

/** Hand-drawn pen circle, absolutely positioned around a word. */
function PenCircle() {
  return (
    <svg className="pen-circle" viewBox="0 0 260 90" preserveAspectRatio="none" aria-hidden="true">
      <path
        d="M196 12 C 120 -2 18 8 12 42 C 7 72 92 86 156 82 C 224 78 254 58 248 36 C 242 15 178 6 138 10"
        fill="none"
      />
    </svg>
  )
}

function HeroEmailMock() {
  const today = new Date()
  const occasion = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7)

  return (
    <div className="hero-mock" aria-hidden="true">
      <div className="hero-mock-leaf">
        <span className="leaf-month">{monthAbbr(occasion.getMonth() + 1)}</span>
        <span className="leaf-day">{occasion.getDate()}</span>
      </div>
      <div className="hero-mock-email">
        <div className="hero-mock-header">
          <span className="hero-mock-from">Wishly</span>
          <span className="hero-mock-addr">reminders@wishly.dev</span>
        </div>
        <p className="hero-mock-subject">Mom’s birthday is in 7 days</p>
        <p className="hero-mock-body">
          Time to prepare — she turns 64 on {monthAbbr(occasion.getMonth() + 1)}{' '}
          {occasion.getDate()}. Your note: “the blue ceramic vase at Harlow&nbsp;&amp;&nbsp;Co.”
        </p>
        <span className="hero-mock-count">In 7 days</span>
      </div>
    </div>
  )
}

const STEPS = [
  {
    title: 'Add the dates',
    body: 'Birthdays, anniversaries, any day you can’t miss. A month and a day is all it takes — years are optional.',
  },
  {
    title: 'Choose your lead time',
    body: '30 days out to order the gift, a week to plan, the day of to make the call. Each date gets its own schedule.',
  },
  {
    title: 'Get the email',
    body: 'Reminders land in your inbox at your hour, in your timezone. Nothing to install, nothing to check.',
  },
] as const

export default function LandingPage() {
  const { isLoaded, isSignedIn } = useWishlyAuth()
  const showOpenApp = isLoaded && isSignedIn

  return (
    <div className="landing">
      <header className="landing-header">
        <Link to="/" className="wordmark">
          wishly<span className="wordmark-dot">.</span>
        </Link>
        <nav className="landing-nav">
          <a href="#how">How it works</a>
          {showOpenApp ? (
            <Link to="/app" className="btn-primary">
              Open app
            </Link>
          ) : (
            <>
              <Link to="/sign-in">Sign in</Link>
              <Link to="/sign-up" className="btn-primary">
                Get started
              </Link>
            </>
          )}
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <h1>
              The dates you’d{' '}
              <span className="circled">
                circle
                <PenCircle />
              </span>{' '}
              on the calendar, remembered for you.
            </h1>
            <p className="hero-sub">
              Wishly keeps the birthdays and anniversaries you care about and emails you before each
              one — with enough lead time to actually do something about it.
            </p>
            <div className="hero-actions">
              <Link to={showOpenApp ? '/app' : '/sign-up'} className="btn-primary btn-large">
                {showOpenApp ? 'Open your dates' : 'Start tracking dates'}
              </Link>
              <a href="#how" className="btn-ghost">
                How it works
              </a>
            </div>
          </div>
          <HeroEmailMock />
        </section>

        <section id="how" className="how">
          <h2>Three steps, then it runs itself</h2>
          <ol className="how-steps">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <span className="how-num">{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="closer">
          <h2>Remembering is the whole gift.</h2>
          <p>Put the dates in once. Wishly does the rest, every year.</p>
          <Link to={showOpenApp ? '/app' : '/sign-up'} className="btn-primary btn-large">
            {showOpenApp ? 'Open your dates' : 'Get started — it’s free'}
          </Link>
        </section>
      </main>

      <footer className="landing-footer">
        <span>
          wishly<span className="wordmark-dot">.</span>
        </span>
        <span>Reminders for the dates that matter.</span>
      </footer>
    </div>
  )
}
