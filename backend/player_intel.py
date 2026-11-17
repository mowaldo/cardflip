"""On-demand player research. No CompsAPI calls, no sports-to-card return prediction."""
import csv, io, math, os, time, threading
from decimal import Decimal
from pathlib import Path
from statistics import mean
import requests
from . import core

LOCK=threading.Lock()
MAX_BYTES=35_000_000
TTL=24
NFL='https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'
NBA='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_{season}.csv'
MLB='https://statsapi.mlb.com/api/v1'

def season_for(league, day=None):
    d=day or core.now().date()
    if league=='NBA':return d.year+(d.month>=10)
    if league=='NFL':return d.year-(d.month<9)
    return d.year-(d.month<4)

def num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (ValueError,TypeError):return None

def minutes(v):
    if ':' in str(v):
        try:
            a,b=str(v).split(':');return int(a)+int(b)/60
        except ValueError:return None
    return num(v)

def metric(label, values):
    v=[x for x in values if x is not None]
    if not v:return None
    # Recent vs previous, non-overlapping; never imply causation or probability.
    recent=v[-5:]; previous=v[-10:-5]
    return {'label':label,'season_avg':round(mean(v),2),'recent_avg':round(mean(recent),2),'recent_n':len(recent),'previous_avg':round(mean(previous),2) if len(previous)>=3 else None,'previous_n':len(previous),'total':round(sum(v),2)}

def _fetch(url,params=None):
    try:
        with requests.get(url,params=params,timeout=(5,20),stream=True,headers={'User-Agent':'CardFlip-Local/1.1 (personal research)'}) as r:
            r.raise_for_status();buf=bytearray();start=time.monotonic()
            for chunk in r.iter_content(65536):
                buf.extend(chunk)
                if len(buf)>MAX_BYTES or time.monotonic()-start>45:raise RuntimeError('Sports data exceeded download limits.')
            return bytes(buf)
    except requests.RequestException as e:raise RuntimeError('Sports data source unavailable. Try again later.') from e

def _dataset(league,season,refresh=False):
    url=(NBA if league=='NBA' else NFL).format(season=season)
    root=Path(os.getenv('CARDFLIP_DB',core.ROOT/'data'/'cardflip.db')).parent/'player_data'
    path=root/f'{league.lower()}-{season}.csv'
    with LOCK:
        if path.exists() and not refresh and time.time()-path.stat().st_mtime<TTL*3600:
            return path.read_bytes(),url,False
        try:
            data=_fetch(url);head=next(csv.reader(io.StringIO(data.decode('utf-8-sig'))),[])
            required={'athlete_display_name','game_id','game_date','season_type'} if league=='NBA' else {'player_display_name','week','season_type'}
            if not required.issubset(head):raise RuntimeError('Sports dataset schema changed; no stats calculated.')
            root.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(path)
            return data,url,False
        except (RuntimeError,UnicodeError,OSError):
            if path.exists():return path.read_bytes(),url,True
            raise RuntimeError('Season dataset unavailable. Check the source or choose a previous season.')

def parse_games(data,league,player,season):
    rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))));name_key='athlete_display_name' if league=='NBA' else 'player_display_name'
    id_key='athlete_id' if league=='NBA' else 'player_id'
    matches=[r for r in rows if core.norm(r.get(name_key,''))==core.norm(player)]
    ids={r.get(id_key) or r.get('player_gsis_id') for r in matches if r.get(id_key) or r.get('player_gsis_id')}
    if len(ids)>1:raise RuntimeError('Multiple players share this name. No automatic match.')
    if league=='NBA':
        games=[r for r in matches if str(r.get('season_type','')).lower() in ('2','regular season','reg') and str(r.get('did_not_play','')).lower() not in ('true','1','t') and (minutes(r.get('minutes')) or 0)>0]
        games.sort(key=lambda r:r.get('game_date',''))
        keys=[('Points','points'),('Rebounds','rebounds'),('Assists','assists'),('Minutes','minutes')]
        datekey='game_date'; dedup='game_id'; teamkey='team_display_name'; poskey='athlete_position_abbreviation'
    else:
        games=[r for r in matches if str(r.get('season_type','')).upper() in ('REG','REGULAR SEASON') and num(r.get('week')) is not None]
        games.sort(key=lambda r:num(r.get('week')) or 0)
        pos=games[-1].get('position','') if games else ''
        keys=([('Passing yards','passing_yards'),('Passing TD','passing_tds'),('Interceptions','passing_interceptions'),('Rushing yards','rushing_yards')] if pos=='QB' else [('Rushing yards','rushing_yards'),('Receiving yards','receiving_yards'),('Receptions','receptions'),('Receiving TD','receiving_tds'),('Rushing TD','rushing_tds')] if pos in ('RB','FB','WR','TE') else [('Tackles solo','def_tackles_solo'),('Sacks','def_sacks'),('Interceptions','def_interceptions')])
        datekey='week';dedup='week';teamkey='team';poskey='position'
    unique={r.get(dedup):r for r in games if r.get(dedup)};games=list(unique.values())
    if not games:raise RuntimeError('No exact-name regular-season player records in this dataset. Check league, spelling or season.')
    metrics=[metric(label,[(minutes if key=='minutes' else num)(r.get(key)) for r in games]) for label,key in keys]
    if not any(metrics):raise RuntimeError('No supported statistics for this player in this dataset.')
    last=games[-1];return {'player':last[name_key],'league':league,'season':season,'team':last.get(teamkey) or last.get('team_name') or last.get('recent_team') or '', 'position':last.get(poskey,''),'sample':len(games),'sample_label':'Recorded player games' if league=='NBA' else 'Recorded player-weeks','through':str(last.get(datekey,'')) if league=='NBA' else 'Week '+str(last.get(datekey,'')),'metrics':[x for x in metrics if x],'metric_mode':'per recorded game/week','notes':['Recent = last five recorded appearances; previous = preceding five (at least three required).','Missing games, injuries and depth-chart changes are not inferred from absent rows.']}

def mlb_fetch(player,season):
    import json
    def get(path,params):return json.loads(_fetch(MLB+path,params))
    data=get('/sports/1/players',{'season':season,'gameType':'R'})
    matches=[p for p in data.get('people',[]) if core.norm(p.get('fullName',''))==core.norm(player)]
    if len(matches)!=1:raise RuntimeError('No unique exact-name MLB player for this season. Minor-league prospects may not be covered.')
    p=matches[0];pid=int(p['id']);metrics=[];samples=[];through=[]
    for group,keys in [('hitting',[('Hits','hits'),('Home runs','homeRuns'),('RBI','rbi'),('Stolen bases','stolenBases')]),('pitching',[('Strikeouts','strikeOuts'),('Earned runs','earnedRuns'),('Hits allowed','hits'),('Walks allowed','baseOnBalls')])]:
        data=get(f'/people/{pid}/stats',{'stats':'gameLog','group':group,'season':season,'gameType':'R','sportId':1})
        rows=[s for g in data.get('stats',[]) for s in g.get('splits',[]) if isinstance(s.get('stat'),dict) and s.get('date')]
        rows.sort(key=lambda s:s['date']);rows=list({str(s.get('game',{}).get('gamePk') or s['date']):s for s in rows}.values())
        if not rows:continue
        samples.append(f'{group}: {len(rows)}');through.append(rows[-1]['date'])
        for label,key in keys:
            m=metric(group.title()+' · '+label,[num(r['stat'].get(key)) for r in rows])
            if m:metrics.append(m)
    if not metrics:raise RuntimeError('No MLB game logs returned for this player and season.')
    return {'player':p['fullName'],'league':'MLB','season':season,'team':p.get('currentTeam',{}).get('name',''),'position':p.get('primaryPosition',{}).get('abbreviation',''),'sample':', '.join(samples),'sample_label':'Recorded appearances','through':max(through),'metrics':metrics,'metric_mode':'per recorded appearance','notes':['Hitting and pitching appearances are separate samples.','Game-log rates do not capture all aspects of player performance.']}

def research(player,league,season=None,refresh=False):
    season=season or season_for(league);key='player-intel:v1:'+core.cache_key({'player':player,'league':league,'season':season});old=core.get_cache(key)
    if old and not refresh and core.age_hours(old[1])<=TTL and not old[0].get('stale'):
        return dict(old[0],origin='cache',fetched=old[1])
    try:
        if league=='MLB':out=mlb_fetch(player,season);source='MLB Stats API';url=MLB+'/sports/1/players';stale=False
        else:
            data,url,stale=_dataset(league,season,refresh);out=parse_games(data,league,player,season);source='SportsDataverse / hoopR (ESPN box scores)' if league=='NBA' else 'nflverse (weekly player stats)'
        out.update(source=source,source_url=url,stale=stale,notes=out['notes']+['Historical performance is not a forecast of card prices. Live injuries, news, population and prospect rankings are not included.'])
        stamp=core.put_cache(key,out);return dict(out,origin='dataset' if league!='MLB' else 'provider',fetched=stamp)
    except (RuntimeError,ValueError,KeyError,TypeError,OSError) as e:
        if old:return dict(old[0],origin='stale cache',stale=True,fetched=old[1],notice='Refresh failed; historical cached stats only.')
        raise RuntimeError(str(e) if isinstance(e,RuntimeError) else 'Unexpected sports data format; no stats calculated.') from e


def hold_scenarios(median,settings,years,annual_target,changes):
    """Hypothetical exit price multiples, not estimated probabilities. Bid before tax/shipping."""
    s=settings;factor=1+s['purchase_tax']/100;results=[]
    for label,pct in zip(('Bear','Flat','Bull'),changes):
        gross=median*(1+pct/100);net=gross*(1-(1+s['buyer_tax']/100)*s['fee']/100)-s['order_fee']-s['outbound']
        max_cost=max(0,min(net-s['min_profit'],net/(1+annual_target/100)**years));bid=core.floor_money(Decimal(str(max_cost/factor-s['inbound'])))
        results.append({'label':label,'change':pct,'exit_price':round(gross,2),'net_proceeds':round(net,2),'max_bid':bid})
    return results
