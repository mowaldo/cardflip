"""Descriptive player momentum and optional NFL report context, not forecasts."""
import csv, io
from . import core, player_intel as pi

INJURY_URL='https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv'
# Thresholds are descriptive heuristics, not calibrated probabilities. Avoid noisy
# percentage changes from zero and avoid treating usage as skill.
METRICS={'Points':(1,2),'Rebounds':(1,1),'Assists':(1,1),'Passing yards':(1,20),'Passing TD':(1,.4),'Interceptions':(-1,.3),'Rushing yards':(1,15),'Receiving yards':(1,15),'Receptions':(1,1),'Receiving TD':(1,.3),'Rushing TD':(1,.3),'Tackles solo':(1,1),'Sacks':(1,.3),'Hitting · Hits':(1,.3),'Hitting · Home runs':(1,.2),'Hitting · RBI':(1,.3),'Pitching · Strikeouts':(1,1),'Pitching · Earned runs':(-1,.5),'Pitching · Walks allowed':(-1,.5)}

def performance(data):
    if data.get('stale') or data.get('season')!=pi.season_for(data['league']):return {'label':'Historical / stale','signals':[]}
    signals=[]
    for m in data.get('metrics',[]):
        if m['label'] not in METRICS or min(m['recent_n'],m['previous_n'])<5 or m['previous_avg'] is None:continue
        direction,floor=METRICS[m['label']];a,b=m['recent_avg'],m['previous_avg'];delta=a-b
        if abs(delta)<max(floor,abs(b)*.10):continue
        signals.append({'metric':m['label'],'delta':round(delta,2),'direction':'positive' if delta*direction>0 else 'negative'})
    # MLB pitching totals depend on innings/role; not a performance verdict.
    if data['league']=='MLB':return {'label':'Review game-log changes','signals':signals}
    good=sum(s['direction']=='positive' for s in signals);bad=len(signals)-good
    enough=any(m['label'] in METRICS and min(m['recent_n'],m['previous_n'])>=5 for m in data.get('metrics',[]))
    label='Limited sample' if not enough else 'Mixed changes' if good and bad else 'Production rising' if good else 'Production weakening' if bad else 'Little recent change'
    return {'label':label,'signals':signals}

def parse_injuries(data,player):
    reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    if not {'full_name','week','date_modified','report_status','practice_status'}.issubset(reader.fieldnames or []):raise RuntimeError('Injury dataset schema changed.')
    rows=[r for r in reader if pi.num(r.get('week')) is not None and str(r.get('game_type') or r.get('season_type') or 'REG').upper() in ('REG','POST','REGULAR SEASON','POSTSEASON')]
    if not rows:raise RuntimeError('No injury reports returned.')
    matches=[r for r in rows if core.norm(r['full_name'])==core.norm(player)]
    ids={r.get('gsis_id') for r in matches if r.get('gsis_id')}
    if len(ids)>1:raise RuntimeError('Ambiguous player name in injury reports.')
    latest=max(int(float(r['week'])) for r in rows)
    coverage=max((r.get('date_modified') or '' for r in rows),default='')[:80]
    def clean(v):return '' if str(v or '').strip().lower() in ('','na','nan','null','none') else str(v)[:150]
    if not matches:return {'status':'No matching report in dataset','latest_week':latest,'coverage_date':coverage,'report':None}
    r=max(matches,key=lambda r:(float(r['week']),r.get('date_modified') or ''))
    report={k:clean(r.get(k)) for k in ('report_status','report_primary_injury','practice_status','practice_primary_injury','date_modified','team')};report['week']=int(float(r['week']))
    return {'status':'Latest recorded report' if report['week']==latest else 'Older report only','latest_week':latest,'coverage_date':coverage,'report':report}

def injury(player,season):
    url=INJURY_URL.format(season=season);key='nfl-injury-dataset:v1:'+str(season);old=core.get_cache(key)
    stale=False
    if old and core.age_hours(old[1])<=6:
        raw=old[0]['csv'];fetched=old[1]
    else:
        try:
            raw=pi._fetch(url).decode('utf-8-sig');parse_injuries(raw.encode(),player)
            fetched=core.put_cache(key,{'csv':raw})
        except (RuntimeError,UnicodeError):
            if not old:raise RuntimeError('Injury reports unavailable.')
            raw=old[0]['csv'];fetched=old[1];stale=True
    out=parse_injuries(raw.encode(),player)
    return dict(out,source_url=url,fetched=fetched,stale=stale,season=season)
