"""On-demand career context from public sports datasets; not a prospect ranking."""
import csv,io,json
from datetime import date
from . import core,player_intel as pi
NFL='https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
NBA='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_core/player_core_{season}.csv'

def clean(v):return str(v or '').strip()[:120] if str(v or '').strip().lower() not in ('','na','nan','null','none') else None

def integer(v):
    n=pi.num(v);return int(n) if n is not None and n.is_integer() and n>=0 else None

def profile(player,league):
    season=pi.season_for(league);key='career:v1:'+core.cache_key({'player':player,'league':league,'season':season});old=core.get_cache(key)
    if old and core.age_hours(old[1])<=24:return dict(old[0],fetched=old[1],stale=False,origin='cache')
    try:
        if league=='MLB':
            url=pi.MLB+'/people/search';data=json.loads(pi._fetch(url,{'names':player}));rows=[p for p in data.get('people',[]) if core.norm(p.get('fullName',''))==core.norm(player)]
            if len(rows)!=1:raise RuntimeError('No unique player bio found.')
            p=rows[0];debut=clean(p.get('mlbDebutDate'));bio={'birth_date':clean(p.get('birthDate')),'debut':debut,'rookie_season':None,'draft_year':None,'draft_pick':None,'position':clean((p.get('primaryPosition') or {}).get('abbreviation')),'experience':None,'stage':'MLB debut recorded' if debut else 'MLB debut not returned'}
        else:
            url=NFL if league=='NFL' else NBA.format(season=season);dk='career-dataset:v1:'+league+(':'+str(season) if league=='NBA' else '');cached=core.get_cache(dk)
            if cached and core.age_hours(cached[1])<=24:raw=cached[0]['csv']
            else:
                raw=pi._fetch(url).decode('utf-8-sig');core.put_cache(dk,{'csv':raw})
            reader=csv.DictReader(io.StringIO(raw));names=('display_name','full_name','athlete_display_name','athlete_full_name','fullName','displayName');available=[n for n in names if n in (reader.fieldnames or [])]
            if not available:raise RuntimeError('Career data schema unavailable.')
            rows=[r for r in reader if any(core.norm(r.get(n,''))==core.norm(player) for n in available)]
            if len(rows)!=1:raise RuntimeError('No unique career profile found.')
            p=rows[0];pick=lambda *keys:next((clean(p.get(k)) for k in keys if clean(p.get(k)) is not None),None)
            draft=integer(pick('draft_year','draftYear','athlete_draft_year'));rookie=integer(pick('rookie_season','rookie_year'));exp=integer(pick('years_of_experience','experience_years','experience','athlete_experience_years'))
            bio={'birth_date':pick('birth_date','date_of_birth','birthdate','dateOfBirth','athlete_date_of_birth'),'debut':None,'rookie_season':rookie,'draft_year':draft,'draft_pick':integer(pick('draft_pick','draft_overall','draft_selection','athlete_draft_pick')),'position':pick('position','position_abbreviation','athlete_position_abbreviation'),'experience':exp,'stage':'Recorded rookie season' if rookie==season else 'Career profile' }
        try:
            b=date.fromisoformat((bio['birth_date'] or '')[:10]);today=core.now().date();age=today.year-b.year-((today.month,today.day)<(b.month,b.day));bio['age']=age if 0<age<110 else None
        except ValueError:bio['age']=None
        out=dict(bio,player=player,league=league,source_url=url);stamp=core.put_cache(key,out);return dict(out,fetched=stamp,stale=False,origin='provider')
    except (RuntimeError,ValueError,TypeError,KeyError,OSError) as e:
        if old:return dict(old[0],fetched=old[1],stale=True,origin='stale cache')
        raise RuntimeError(str(e) if isinstance(e,RuntimeError) else 'Career profile unavailable.') from e

MINORS={11:'Triple-A',12:'Double-A',13:'High-A',14:'Single-A',16:'Rookie'}
def minor_stats(player,season):
    key='minor-stats:v1:'+core.cache_key({'player':player,'season':season});old=core.get_cache(key)
    if old and core.age_hours(old[1])<=24:return dict(old[0],fetched=old[1],origin='cache',stale=False)
    try:
        search=pi.MLB+'/people/search';data=json.loads(pi._fetch(search,{'names':player}));matches=[p for p in data.get('people',[]) if core.norm(p.get('fullName',''))==core.norm(player)]
        if len(matches)!=1:raise RuntimeError('No unique baseball player found.')
        pid=int(matches[0]['id']);url=pi.MLB+f'/people/{pid}/stats';out=[]
        for group in ('hitting','pitching'):
            raw=json.loads(pi._fetch(url,{'stats':'season','season':season,'group':group,'sportIds':'11,12,13,14,16','gameType':'R'}))
            for block in raw.get('stats',[]):
                for split in block.get('splits',[]):
                    sport=split.get('sport') or {};sid=integer(sport.get('id'));stat=split.get('stat') or {}
                    # Refuse to infer MiLB level from request parameters: server may ignore filters.
                    if sid not in MINORS or not isinstance(stat,dict) or str(split.get('season') or season)!=str(season):continue
                    team=clean((split.get('team') or {}).get('name'));metrics={k:clean(stat.get(k)) for k in (('gamesPlayed','plateAppearances','avg','ops','homeRuns','stolenBases') if group=='hitting' else ('gamesPlayed','inningsPitched','era','whip','strikeOuts'))}
                    if any(v is not None for v in metrics.values()):out.append({'level':MINORS[sid],'team':team,'group':group,'metrics':metrics})
        result={'player':player,'season':season,'rows':out,'source_url':url};fetched=core.put_cache(key,result);return dict(result,fetched=fetched,origin='provider',stale=False)
    except (RuntimeError,ValueError,TypeError,KeyError,OSError) as e:
        if old:return dict(old[0],fetched=old[1],origin='stale cache',stale=True)
        raise RuntimeError(str(e) if isinstance(e,RuntimeError) else 'Minor league data unavailable.') from e
