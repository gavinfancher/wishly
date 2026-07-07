const ONBOARDING_KEY = 'wishly:onboarding_done'

/** Persist that this user has completed onboarding (same-browser skip). */
export function markOnboardingDone(userId: string): void {
  localStorage.setItem(`${ONBOARDING_KEY}:${userId}`, '1')
}

export function isOnboardingDone(userId: string): boolean {
  return localStorage.getItem(`${ONBOARDING_KEY}:${userId}`) === '1'
}
