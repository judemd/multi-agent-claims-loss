"""Labels leave this module only through the explicit evaluation payload."""
import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import dump_claims_csv
from .schemas import Bulletin, Claim


def generate(seed=42, held_out=False):
    rng = random.Random(seed)
    claims, labels, duplicates, bulletins = [], {}, {}, []
    causes = ['power outage', 'surface water flood', 'wind damage']
    dev = [
        ['Supply failed and refrigeration stopped.', 'Lights went out across the street; our electrical equipment stopped.', 'A district electricity interruption shut down production.'],
        ['Water came through the doors after heavy rain.', 'Surface flooding soaked the stock room.', 'Rainwater collected outside and entered the loading bay.'],
        ['Strong gusts tore roofing and damaged stock.', 'A windstorm lifted roof sheets; rain reached equipment.', 'Flying debris and violent winds interrupted operations.']]
    held = [
        ['The mains went dead; chilled goods warmed overnight.', 'Neighbours also lost power; a voltage disturbance preceded our shutdown.', 'The electricity network failed and deliveries had to stop.'],
        ['Runoff entered at floor level and soaked inventory.', 'An overflowing street channel sent water into the premises.', 'Intense rainfall overwhelmed drains and submerged the lower store.'],
        ['Roof panels lifted in violent weather.', 'A squall stripped the canopy and exposed stored materials.', 'Airborne fragments struck equipment during exceptional gusts.']]
    centers = [(20, 20), (55, 60), (80, 25)]
    start = datetime(2026, 1, 10, 9, tzinfo=timezone.utc)
    def make(index, x, y, incident, narrative, cause):
        return Claim(claim_id=f'C{index:03}', business_name=f'Fictional Business {index}',
                     notification_timestamp=(incident or start) + timedelta(days=rng.randint(1, 8)),
                     incident_start=incident, incident_end=incident + timedelta(hours=2) if incident else None,
                     x=x, y=y, business_type=rng.choice(['restaurant', 'shop', 'warehouse']),
                     loss_type=rng.choice(['stock', 'equipment', 'interruption']), narrative=narrative,
                     reported_amount_gbp=None if rng.random() < .12 else rng.randrange(100, 50000))
    for event, (x, y) in enumerate(centers):
        when = start + timedelta(days=event * 3)
        for j in range(10):
            t = when + timedelta(hours=rng.uniform(-2, 2))
            if j == 0:
                t = None
            if j == 1:
                t = when + timedelta(days=2)  # Deliberate structured-time contradiction.
            narrative = rng.choice((held if held_out else dev)[event]) + f' Staff account {rng.randrange(10000)}.'
            c = make(len(claims)+1, x+rng.uniform(-3, 3), y+rng.uniform(-3, 3), t, narrative, causes[event])
            claims.append(c)
            labels[c.claim_id] = f'E{event+1}'
        bulletins.append(Bulletin(bulletin_id=f'B{event+1}', start=when, end=when+timedelta(hours=5),
                                 x=x+2, y=y-1, radius_km=7, description=f'Unconfirmed reports of {causes[event]} in part of the area.'))
    for j in range(18):
        # Includes similar language at a different time/location and unrelated local incidents.
        narrative = (rng.choice((held if held_out else dev)[j % 3]) if j % 2 else 'A local appliance failed internally; no neighbouring premises affected.')
        c = make(len(claims)+1, rng.uniform(0,100), rng.uniform(0,100), start+timedelta(days=rng.randint(0,20)), narrative, 'local')
        claims.append(c)
        labels[c.claim_id] = f'isolated-{j}'
    for original in [claims[3], claims[16]]:
        new_id = f'C{len(claims)+1:03}'
        c = original.model_copy(update={'claim_id':new_id, 'notification_timestamp':original.notification_timestamp+timedelta(days=1)})
        claims.append(c)
        labels[new_id] = labels[original.claim_id]
        duplicates[new_id] = original.claim_id
    rng.shuffle(claims)
    irrelevant = Bulletin(bulletin_id='B4',start=start+timedelta(days=25),end=start+timedelta(days=25,hours=1),
                          x=5,y=90,radius_km=3,description='An unverified electrical disturbance was reported near a remote maintenance depot.')
    return claims, bulletins[:2]+[irrelevant], dict(events=labels, duplicates=duplicates, seed=seed, held_out=held_out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='fixtures')
    args = parser.parse_args()
    root = Path(args.output)
    for name, seed, held in [('development',42,False)] + [(f'held_out_{n}',100+n,True) for n in range(5)]:
        claims, bulletins, truth = generate(seed,held)
        folder = root/name
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'claims.csv').write_text(dump_claims_csv(claims),encoding='utf-8')
        (folder/'bulletins.json').write_text(json.dumps([b.model_dump(mode='json') for b in bulletins],indent=2),encoding='utf-8')
        hidden = root/'ground_truth'
        hidden.mkdir(exist_ok=True)
        (hidden/f'{name}.json').write_text(json.dumps(truth,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
