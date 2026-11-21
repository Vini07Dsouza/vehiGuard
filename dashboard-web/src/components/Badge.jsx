import { nice } from '../format'

// One small coloured label for severities, statuses, outcomes and camera states.
const TONES = {
  HIGH: 'danger',
  MEDIUM: 'warn',
  LOW: 'info',
  INFO: 'muted',
  NEW: 'danger',
  ACKNOWLEDGED: 'warn',
  UNDER_INVESTIGATION: 'info',
  CLOSED_CONFIRMED: 'ok',
  CLOSED_FALSE_ALARM: 'muted',
  REPORTED: 'warn',
  DETECTED: 'danger',
  RECOVERED: 'ok',
  CLOSED: 'muted',
  PASS: 'ok',
  STOLEN_MATCH: 'danger',
  MISSING_MATCH: 'danger',
  SUSPECTED_CLONE: 'warn',
  APPEARANCE_MISMATCH: 'info',
  UNKNOWN_PLATE: 'muted',
  POSSIBLE_MATCH: 'warn',
  NO_PLATE: 'muted',
  LOW_CONFIDENCE: 'muted',
  ONLINE: 'ok',
  OFFLINE: 'danger',
  STOPPED: 'muted',
}

export default function Badge({ value }) {
  return <span className={`badge ${TONES[value] || 'muted'}`}>{nice(value)}</span>
}
