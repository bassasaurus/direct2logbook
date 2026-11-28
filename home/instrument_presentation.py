"""Concise web/mobile display of the shared instrument-recency calculation."""
from logbook.date_formats import display_date


def instrument_presentation(snapshot, *, today=None):
    from django.utils import timezone
    today = today or timezone.localdate()
    current = snapshot['ifr_current']
    due = snapshot['instrument_review_date']
    ipc_current = current and snapshot['instrument_currency_source'] == 'ipc'
    ipc_required = snapshot['ipc_required']
    count = snapshot['appr_quantity']
    missing = snapshot['still_needed']
    holding = bool(snapshot['hold_quantity'])
    source = ('Logged approaches and holding' if snapshot['instrument_currency_source'] == 'recency'
              else 'IPC' if ipc_current else '')
    expired = bool(due and due < today)
    status = 'Until ' + display_date(due) if current else 'Expired ' + display_date(due) if expired else 'Review logged experience'
    approach_text = f'{count}/6'
    if missing and not ipc_current and not ipc_required:
        approach_text += f' - Log {missing} more'
    holding_text = ('Logged ' + display_date(snapshot['hold_current_date']) if holding
                    else 'Not separately logged' if ipc_current
                    else 'Holding required' if count > 0 else 'Not logged')
    if ipc_required:
        next_action = 'An IPC may be required. Record an IPC or correct missing entries.'
    else:
        next_action = snapshot['next_instrument_requirement']['message']
    return {
        'status': status, 'tone': 'success' if current else 'danger' if expired else 'warning',
        'basis': source, 'approaches': approach_text,
        'approach_tone': 'success' if count >= 6 else 'muted' if ipc_current else 'danger',
        'holding': holding_text, 'holding_tone': 'success' if holding else 'muted' if ipc_current or not count else 'danger',
        'next_action': next_action,
        'ipc_summary': {
            'logged_date': snapshot['ipc_completed_date'],
            'expiry_date': snapshot['ipc_review_due_date'],
        } if snapshot['ipc_completed_date'] and count == 0 else None,
        'ipc_review_from': snapshot['ipc_required_from'] if not current and not ipc_required else None,
        'window_start': snapshot['instrument_window_start'],
        'approach_dates': [display_date(day).split(',')[0] for day in reversed(snapshot.get('instrument_approach_dates', []))],
    }
