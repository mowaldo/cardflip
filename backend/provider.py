import os, requests

def fetch(card, broad=False):
    key=os.getenv('COMPSAPI_KEY','').strip()
    if not key: raise RuntimeError('No API key configured. Add COMPSAPI_KEY to .env and restart, or try demo mode.')
    raw=card['grader']=='RAW'
    query=' '.join(x for x in [card['year'],card['player'],card['set'],card['number'],'' if broad or card['variant'].lower() in ('base','autograph insert') else card['variant'], '' if raw else card['grader'],card.get('grade_type',''),card['grade']] if x)
    params={'q':query,'days':90,'size':240 if broad or raw or card.get('print_run') else 100,'cards':1,'grader':card['grader'],'grade':card['grade'],'best_offer':1,'site':'US'}
    if raw:
        params.pop('grader');params.pop('grade');params['graded']='false'
    try:
        r=requests.get('https://api.compsapi.com/v1/sold',params=params,headers={'X-API-Key':key,'User-Agent':'CardFlipLocal/0.8'},timeout=(2,8))
    except requests.RequestException as e: raise RuntimeError('Provider connection failed. Check network and try later.') from e
    if r.status_code==429: raise RuntimeError('Provider rate or monthly quota reached. No automatic retry.')
    if r.status_code!=200: raise RuntimeError(f'Provider returned HTTP {r.status_code}. Check your API key and query.')
    try: data=r.json()
    except ValueError as e: raise RuntimeError('Provider returned invalid JSON.') from e
    if not isinstance(data,dict) or data.get('ok') is False or not isinstance(data.get('items'),list): raise RuntimeError('Unexpected provider response; no data cached.')
    return data['items']

def fetch_board(card):
    key=os.getenv('COMPSAPI_KEY','').strip()
    if not key: raise RuntimeError('No API key configured. Add COMPSAPI_KEY to .env and restart.')
    query=' '.join(card[k] for k in ('player','year','set','number') if card.get(k))
    params={'q':query,'days':90,'size':240,'cards':1,'best_offer':1,'site':'US','exclude':'junk'}
    try:
        r=requests.get('https://api.compsapi.com/v1/sold',params=params,headers={'X-API-Key':key,'User-Agent':'CardFlipLocal/0.9'},timeout=(2,8))
    except requests.RequestException as e:raise RuntimeError('Provider connection failed. Check network and try later.') from e
    if r.status_code!=200:raise RuntimeError(f'Provider returned HTTP {r.status_code}. No automatic retry.')
    try:data=r.json()
    except ValueError as e:raise RuntimeError('Provider returned invalid JSON.') from e
    if not isinstance(data,dict) or data.get('ok') is False or not isinstance(data.get('items'),list):raise RuntimeError('Unexpected provider response.')
    return data['items']
