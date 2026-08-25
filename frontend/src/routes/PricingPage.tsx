import { Link } from 'react-router-dom'

import PenCircle from '../components/PenCircle.tsx'
import { MarketingFooter, MarketingHeader } from '../components/MarketingChrome.tsx'

/**
 * Public pricing page at `/pricing`.
 *
 * Nothing here charges money yet — there is no billing wired up — so both
 * buttons lead to sign-up and the Pro panel says so plainly rather than faking
 * a checkout. The signature is the landing page's pen circle, drawn this time
 * around the yearly price: the plan you'd circle.
 */

const FREE_LINES = [
  '5 dates',
  'Up to 3 reminders on each one',
  'Your send hour, your timezone',
  'Runs every year without touching it',
] as const

const PRO_LINES = [
  'Unlimited dates',
  'Unlimited reminders on each one',
  'Everything in Free',
] as const

const QUESTIONS = [
  {
    q: 'What counts as a date?',
    a: 'One birthday or anniversary. Each date carries its own reminders — say 30 days out to order something, a week out to plan, and the morning of.',
  },
  {
    q: 'Do the reminders differ by plan?',
    a: 'No. Same sender, same timing, same email. Pro lifts the counts, nothing else.',
  },
  {
    q: 'Do I need a card to start?',
    a: 'No. Free is free, and Pro billing is not open yet — start now and upgrade in place when it is.',
  },
] as const

export default function PricingPage() {
  return (
    <div className="landing">
      <MarketingHeader />

      <main>
        <section className="pricing-hero">
          <h1>Two plans. One of them is free.</h1>
          <p>
            Wishly is cheap to run, so it is cheap to use. Start free, and pay only once you are
            tracking more than a handful of dates.
          </p>
        </section>

        <section className="pricing-plans">
          <article className="plan">
            <h2 className="plan-name">Free</h2>
            <p className="plan-price">
              <span className="plan-price-num">$0</span>
              <span className="plan-cadence">always</span>
            </p>
            <p className="plan-blurb">Enough for the dates you would actually circle.</p>
            <ul className="plan-list">
              {FREE_LINES.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <Link to="/sign-up" className="btn-secondary plan-cta">
              Get started
            </Link>
          </article>

          <article className="plan plan-pro">
            <h2 className="plan-name">Pro</h2>
            <p className="plan-price">
              <span className="plan-price-num circled">
                $10
                <PenCircle />
              </span>
              <span className="plan-cadence">a year</span>
            </p>
            <p className="plan-alt">or $2 a month</p>
            <p className="plan-blurb">Every date you keep, however you want reminding.</p>
            <ul className="plan-list">
              {PRO_LINES.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <Link to="/sign-up" className="btn-primary plan-cta">
              Start free
            </Link>
            <p className="plan-note">Billing is not open yet — everyone starts on Free.</p>
          </article>
        </section>

        <section className="pricing-qa">
          {QUESTIONS.map((item) => (
            <div className="pricing-qa-item" key={item.q}>
              <h3>{item.q}</h3>
              <p>{item.a}</p>
            </div>
          ))}
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
