import json
from datetime import datetime, timezone

ZONES = {
    'sub1': 'Zone 1 (kitchen circuits)',
    'sub2': 'Zone 2 (laundry, fridge, lights)',
    'sub3': 'Zone 3 (water heater, AC)',
    'unmetered': 'Unmetered circuits',
}
PROTECTED = {'sub2'}  # contains a refrigerator: never auto-cut


def build_commands(zone_w, min_w=10.0):
    cmds = []
    for zone, watts in zone_w.items():
        if watts < min_w:
            continue
        protected = zone in PROTECTED
        cmds.append({
            'zone': zone,
            'label': ZONES[zone],
            'night_avg_watts': round(watts, 1),
            'action': 'MONITOR_ONLY' if protected else 'SWITCH_OFF_01:00_05:00',
            'status': 'NO_ACTION' if protected else 'PENDING_HUMAN_APPROVAL',
        })
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'recommend_only',
        'commands': cmds,
    }
    return json.dumps(payload, indent=2)