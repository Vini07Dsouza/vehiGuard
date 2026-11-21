// Reason codes in plain language, so an alert can be understood from the screen alone.
const REASONS = {
  STOLEN_REPORT_MATCH: 'The plate matches an open STOLEN report.',
  MISSING_REPORT_MATCH: 'The plate matches an open MISSING report.',
  IMPOSSIBLE_JOURNEY:
    'The same plate was seen at another camera too recently for a vehicle to have travelled between them.',
  SIGHTING_APPEARANCE_MISMATCH: 'The vehicle looks different from the earlier sighting of this plate.',
  REGISTRY_APPEARANCE_MISMATCH: 'The vehicle looks different from what the registry says for this plate.',
  APPEARANCE_MISMATCH:
    'The vehicle also looks different from the registry, so the plate may have been copied from a stolen vehicle.',
  UNKNOWN_PLATE: 'The plate is not in the vehicle registry.',
  FLAG_UNREGISTERED: 'Alerts on unregistered plates are switched on.',
  POSSIBLE_MATCH: 'The plate is one character away from a stolen or missing plate. For review only.',
  REGISTERED: 'The plate is in the registry.',
  NO_PLATE: 'No readable plate was found.',
  LOW_CONFIDENCE: 'A plate was found but could not be read reliably.',
}

export const reasonText = (code) => REASONS[code] || code

// The one-line headline for an alert type
export const HEADLINES = {
  STOLEN_VEHICLE: 'Stolen vehicle seen',
  MISSING_VEHICLE: 'Missing vehicle seen',
  SUSPECTED_CLONE: 'Suspected cloned plate',
  APPEARANCE_MISMATCH: 'Vehicle does not look like its registration',
  UNREGISTERED_VEHICLE: 'Unregistered vehicle seen',
}

export const ALERT_STATUSES = [
  'NEW',
  'ACKNOWLEDGED',
  'UNDER_INVESTIGATION',
  'CLOSED_CONFIRMED',
  'CLOSED_FALSE_ALARM',
]
export const ALERT_TYPES = Object.keys(HEADLINES)
export const SEVERITIES = ['HIGH', 'MEDIUM', 'LOW', 'INFO']
export const RECOVERY_STATUSES = [
  'REPORTED',
  'DETECTED',
  'UNDER_INVESTIGATION',
  'RECOVERED',
  'CLOSED',
]
