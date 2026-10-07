import { Link } from 'react-router-dom'

import { LoginLink } from '../components/MarketingChrome.tsx'
import { Icon, Message, TitleBar } from '../components/Win98.tsx'

/**
 * Public marketing page at `/`: one Windows 98 application window.
 *
 * The headline sits beside the actual (plain-text) reminder email, word for
 * word, so the product explains itself.
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
function HeroEmail() {
  const today = new Date()
  const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7)

  return (
    <fieldset className="groupbox hero-mail" aria-hidden="true">
      <legend>Example e-mail</legend>
      <div className="mailhead">
        <span>From:</span>
        <span>Wishly &lt;reminders@wishly.dev&gt;</span>
        <span>Subject:</span>
        <span>In 7 days: Mom’s birthday</span>
      </div>
      <div className="mailbody">
        <p>
          Mom’s birthday is on {MONTHS[date.getMonth()]} {date.getDate()}.
        </p>
        <p>— Wishly</p>
      </div>
    </fieldset>
  )
}

const STEPS = [
  {
    icon: 'calendar',
    title: 'Pick a date',
    body: 'A birthday, an anniversary, a renewal deadline — any day that comes back every year.',
  },
  {
    icon: 'clock',
    title: 'Pick when to hear about it',
    body: '30 days out to order the gift, 7 to plan, the day of to call. As many as you like.',
  },
  {
    icon: 'mail',
    title: 'Get a plain email',
    body: 'One short email per reminder, at the hour you choose. No app to open.',
  },
] as const

export default function LandingPage() {
  return (
    <div className="screen">
      <main className="window app-window" aria-label="Wishly">
        <TitleBar title="Welcome - Wishly" icon="wishly" themeToggle />

        <div className="pane landing-pane">
          <div className="scroll">
            <div className="landing">
              <section className="hero">
                <div className="hero-copy">
                  <h1>The dates you’d circle on the calendar, remembered for you.</h1>
                  <p>
                    Pick a date and how many days ahead you want to know. Wishly emails you then —
                    every year, with enough lead time to actually do something about it.
                  </p>
                  <div className="row">
                    <Link to="/sign-up" className="btn">
                      Get Started
                    </Link>
                    <LoginLink className="btn">Log In...</LoginLink>
                  </div>
                </div>
                <HeroEmail />
              </section>

              <section id="how" className="how">
                <h2>Two choices, then it runs itself</h2>
                <ol className="how-steps">
                  {STEPS.map((step, index) => (
                    <li key={step.title}>
                      <Icon name={step.icon} size={32} />
                      <div>
                        <h3>
                          {index + 1}. {step.title}
                        </h3>
                        <p>{step.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>

              <section className="closer">
                <Message icon="info">
                  <p>
                    <b>Remembering is the whole gift.</b>
                  </p>
                  <p>Put the dates in once. Wishly does the rest, every year.</p>
                </Message>
              </section>
            </div>
          </div>
        </div>

        <div className="statusbar">
          <div className="statusbar-main">Reminders for the dates that matter.</div>
          <div>wishly.dev</div>
        </div>
      </main>
    </div>
  )
}
