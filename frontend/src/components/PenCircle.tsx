/**
 * Hand-drawn pen circle, absolutely positioned around a word.
 *
 * `pathLength` normalizes the stroke to 700 units so the dash animation in
 * `index.css` (`stroke-dasharray/-dashoffset: 700`) spans exactly the whole
 * path. The real geometry is ~588 units, and `vector-effect: non-scaling-stroke`
 * makes the browser resolve dashes in *screen pixels* — so without this the
 * circle fails to close at large font sizes or browser zoom, and finishes early
 * then visibly stalls at small ones.
 *
 * Wrap the target in `.circled` — the circle positions itself off that.
 */
export default function PenCircle() {
  return (
    <svg className="pen-circle" viewBox="0 0 260 90" preserveAspectRatio="none" aria-hidden="true">
      <path
        d="M196 12 C 120 -2 18 8 12 42 C 7 72 92 86 156 82 C 224 78 254 58 248 36 C 242 15 178 6 138 10"
        fill="none"
        pathLength={700}
      />
    </svg>
  )
}
