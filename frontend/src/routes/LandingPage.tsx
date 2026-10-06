import { Link } from 'react-router-dom'

import PenCircle from '../components/PenCircle.tsx'
import { MarketingFooter, MarketingHeader } from '../components/MarketingChrome.tsx'
import { monthAbbr } from '../lib/dates.ts'

/**
 * Public marketing page at `/`.
 *
 * The signature visual is the red pen circle — the mark you'd draw around a
 * date on a wall calendar — around the word "circle" in the headline, echoed
 * by a mock of the actual (plain-text) reminder email in the hero.
 */

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const

/** The real email, word for word: plain text, subject + one line. */
function HeroEmailMock() {
  const today = new Date()
  const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7)

  return (
    <div className="hero-mock" aria-hidden="true">
      <div className="hero-mock-leaf">
        <span className="leaf-month">{monthAbbr(date.getMonth() + 1)}</span>
        <span className="leaf-day">{date.getDate()}</span>
      </div>
      <div className="hero-mock-email">
        <div className="hero-mock-header">
          <span className="hero-mock-from">Wishly</span>
          <span className="hero-mock-addr">reminders@wishly.dev</span>
        </div>
        <p className="hero-mock-subject">In 7 days: Mom’s birthday</p>
        <p className="hero-mock-body">
          Mom’s birthday is on {MONTHS[date.getMonth()]} {date.getDate()}.
          <br />
          <br />— Wishly
        </p>
      </div>
    </div>
  )
}

const STEPS = [
  {
    title: 'Pick a date',
    body: 'A birthday, an anniversary, a renewal deadline — any day that comes back every year.',
  },
  {
    title: 'Pick when to hear about it',
    body: '30 days out to order the gift, 7 to plan, the day of to call. As many as you like.',
  },
  {
    title: 'Get a plain email',
    body: 'One short email per reminder, at the hour you choose. No app to open.',
  },
] as const

export default function LandingPage() {
  return (
    <div className="landing">
      <MarketingHeader />

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
              Pick a date and how many days ahead you want to know. Wishly emails you then — every
              year, with enough lead time to actually do something about it.
            </p>
            <div className="hero-actions">
              <Link to="/sign-up" className="btn-primary btn-large">
                Get started
              </Link>
            </div>
          </div>
          <HeroEmailMock />
        </section>

        <section id="how" className="how">
          <h2>Two choices, then it runs itself</h2>
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
        </section>
      </main>

      <MarketingFooter />
    </div>
  )
}
