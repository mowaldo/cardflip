"""Local-only pricing, cache and matching helpers."""
import os, re, json, sqlite3, time, math, unicodedata
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from contextlib import contextmanager
from statistics import median

ROOT = Path(__file__).resolve().parents[1]

def now(): return datetime.now(timezone.utc)
def stamp(): return now().isoformat()
def parse_date(s):
    try:
        d = datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return d.replace(tzinfo=timezone.utc) if not d.tzinfo else d.astimezone(timezone.utc)
    except (ValueError, TypeError): return None

def norm(s):
    s = unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z0-9]+',s))

def phrase(t, p): return f' {norm(p)} ' in f' {norm(t)} '
def cache_key(card): return json.dumps({k:norm(v) for k,v in card.items()},sort_keys=True,separators=(',',':'))

@contextmanager
def connection():
    path = Path(os.getenv('CARDFLIP_DB',ROOT/'data'/'cardflip.db'))
    path.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=15)
    c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS attempts (at REAL NOT NULL)')
    try:
        with c:
            yield c
    finally:
        c.close()

def get_cache(key):
    with connection() as c:
        row=c.execute('SELECT payload,fetched FROM cache WHERE key=?',(key,)).fetchone()
    if not row: return None
    return json.loads(row['payload']),row['fetched']

def put_cache(key,payload,fetched=None):
    fetched=fetched or stamp()
    with connection() as c:
        c.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,json.dumps(payload),fetched))
    return fetched

def age_hours(fetched): return max(0,(now()-parse_date(fetched)).total_seconds()/3600)
def month_start(): return now().replace(day=1,hour=0,minute=0,second=0,microsecond=0).timestamp()
def used():
    with connection() as c: return c.execute('SELECT count(*) FROM attempts WHERE at>=?',(month_start(),)).fetchone()[0]

def budget(): return min(100,max(0,int(os.getenv('MONTHLY_LIMIT','100'))))

def reserve():
    # Count attempts, not just successes, to remain conservative even if a request times out.
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT count(*) FROM attempts WHERE at>=?',(month_start(),)).fetchone()[0]>=budget():
            raise RuntimeError('Local monthly request cap reached. Use cached results or wait for next UTC month.')
        if c.execute('SELECT count(*) FROM attempts WHERE at>=?',(time.time()-60,)).fetchone()[0]>=10:
            raise RuntimeError('Local rate cap reached. Wait one minute before another fresh lookup.')
        c.execute('INSERT INTO attempts VALUES (?)',(time.time(),))

PARALLELS = r'\b(silver|refractor|holo|hyper|wave|disco|fast break|cracked ice|ice|pulsar|choice|mojo|scope|shimmer|sparkle|white|black|gold|green|blue|red|pink|purple|orange|bronze|copper|tie dye|animal print|zebra|tiger|snakeskin|genesis|peacock|velocity|checkerboard|laser|fluorescent|atomic|variation|parallel|short print|ssp|sapphire|reverse|prizm parallel|no huddle|ruby|emerald|x fractor|xfractor|diamond|platinum|cosmic|lazer|kaboom|downtown|color blast|stained glass|superfractor|die cut|insert)\b'
JUNK = r'\b(lot|bundle|reprint|custom|proxy|digital|replica|facsimile|break|pack|box|case|team set|you pick|read description|damaged|cracked slab)\b'
SPECIAL = r'\b(autograph|autographed|auto|patch|relic)\b'

def candidate(item, card, identity_only=False):
    title=str(item.get('title','')); t=norm(title); meta=item.get('card') or {}
    if not isinstance(meta,dict): meta={}
    try:
        price=float(item['price']); ship=item.get('shipping_cost'); ship=None if ship is None else float(ship)
        if not math.isfinite(price) or price<=0 or (ship is not None and (not math.isfinite(ship) or ship<0)): return None
    except (KeyError,ValueError,TypeError): return None
    dt=parse_date(item.get('last_sold')); ident=str(item.get('item_id') or '')
    if not dt or dt>now()+timedelta(minutes=5) or not ident: return None
    if not all(phrase(t,card[k]) for k in ('year','player','set')): return None
    # Number must be visibly labeled or parsed. Bare numbers are ambiguous.
    number=norm(card['number']); parsed=norm(meta.get('card_number') or '')
    if number and parsed!=number and not re.search(r'(?:#\s*|\b(?:no\.?|card)\s+)' + re.escape(card['number']) + r'(?![\w/])',title,re.I): return None
    if card['grader']=='RAW':
        if meta.get('graded') is True or meta.get('grader') or meta.get('grade') or re.search(r'\b(?:psa|bgs|sgc|cgc|tag|beckett|graded|slabbed)\b',t):return None
        if str(meta.get('condition') or '').lower() in ('lp','mp','hp','dmg') or re.search(r'\b(?:damaged|crease|creased|poor condition|lightly played|heavily played)\b',t):return None
    else:
        try: grade_match = float(meta.get('grade')) == float(card['grade'])
        except (ValueError,TypeError): grade_match = False
        if norm(meta.get('grader') or '')!=norm(card['grader']) or not grade_match:
            if meta.get('grader') or meta.get('grade'): return None
            if not re.search(r'\b'+re.escape(card['grader'])+r'\s*(?:(?:pristine|gem mint|perfect|black label)\s*)?'+re.escape(card['grade'])+r'(?![\d.])',title,re.I): return None
    # Exact grade designation matters for 10s: never mix Pristine, Gem Mint or Black Label.
    grade_type=norm(card.get('grade_type',''))
    if card['grader'] in ('CGC','BGS','SGC') and str(card['grade'])=='10':
        if not grade_type or not phrase(t,grade_type): return None
        if grade_type=='pristine' and re.search(r'\b(?:black label|gem mint|perfect)\b',t):return None
        if grade_type=='gem mint' and re.search(r'\b(?:pristine|black label|perfect)\b',t):return None
        if grade_type=='perfect' and re.search(r'\b(?:pristine|black label|gem mint)\b',t):return None
        if grade_type=='black label' and re.search(r'\b(?:gem mint|perfect)\b',t):return None
    # Grading-label colors are not card parallels. Strip only explicit label phrases.
    if grade_type=='pristine': t=re.sub(r'\bgold label\b','',t)
    if grade_type=='black label': t=re.sub(r'\bblack label\b','',t)
    # Exclude obvious incompatible listings. Human confirmation still required for every row.
    variant=norm(card['variant']); flags=[]
    if re.search(JUNK,t): return None
    # Remove product name before parallel screening (e.g. Topps Chrome Black).
    edition=re.sub(r'\b'+re.escape(norm(card['set']))+r'\b',' ',t)
    runs=re.findall(r'(?<![\w/])(?:\d{1,6})?\s*/\s*(\d{1,6})\b',title)
    run=card.get('print_run','')
    if run:
        if not runs or set(str(int(x)) for x in runs)!={run}:return None
    elif runs:return None
    special=lambda val: (bool(re.search(r'\b(?:auto|autograph|autographed)\b',val)),bool(re.search(r'\b(?:patch|relic)\b',val)))
    if special(edition)!=special(variant):return None
    if identity_only:
        pass
    elif variant=='base':
        if re.search(PARALLELS,edition): return None
        if meta.get('flags') and any('parallel' in str(f).lower() or 'numbered' in str(f).lower() for f in meta['flags']): return None
    else:
        # Normalize common autograph wording while keeping parallel/insert evidence separate.
        canonical=lambda v:re.sub(r'\b(?:auto|autographed)\b','autograph',v)
        v=canonical(variant); ed=canonical(edition)
        if not phrase(ed,v):
            if v=='autograph insert' and phrase(ed,'autograph'):flags.append('Generic autograph candidate; verify exact insert and parallel')
            else:return None
        remaining=re.sub(r'\b'+re.escape(v)+r'\b',' ',ed)
        if v=='autograph insert':remaining=re.sub(r'\b(?:autograph|insert)\b',' ',remaining)
        if re.search(PARALLELS,remaining):return None
    if card['grader']=='RAW':flags.append('Raw condition and exact edition need visual review')
    if ship is None: flags.append('Buyer shipping unknown')
    if item.get('best_offer') is True: flags.append('Accepted offer (provider reported)')
    return {'id':ident,'title':title[:500],'price':round(price,2),'shipping':ship,'date':dt.isoformat(),'url':str(item.get('url') or ''),'flags':flags}

def matches(items,card):
    result={}
    for item in items:
        if not isinstance(item,dict): continue
        row=candidate(item,card)
        if row and row['id'] not in result: result[row['id']]=row
    return sorted(result.values(),key=lambda r:r['date'],reverse=True)

def D(x): return Decimal(str(x))
def money(x): return float(x.quantize(D('.01'),rounding=ROUND_HALF_UP))
def floor_money(x): return float(max(D(0),x).quantize(D('.01'),rounding=ROUND_FLOOR))

def calculate(rows, settings, fetched, source):
    # All recent explicitly confirmed matches; estimate total buyer-paid price before tax.
    rows=sorted(rows,key=lambda x:x['date'],reverse=True)
    recent=[r for r in rows if (now()-parse_date(r['date'])).days<90]
    last30=sum((now()-parse_date(r['date'])).days<30 for r in recent)
    base={'count':len(recent),'last30_sample':last30,'rows':recent,'median':None,'estimate':None,'profit':None,'roi':None,'max_bid':None,'recommendation':'INSUFFICIENT DATA','reason':'Confirm at least five exact sales from the last 90 days.'}
    if len(recent)<5: return base
    vals=sorted(D(r['price'])+D(r['shipping'] or 0) for r in recent)
    med=median(vals)
    # Lower quartile, linear interpolation, conservative relative to median.
    pos=D(len(vals)-1)*D('.25'); i=int(pos); q=vals[i]+(vals[min(i+1,len(vals)-1)]-vals[i])*(pos-i)
    s={k:D(v) for k,v in settings.items()}
    resale=q*(1-s['haircut']/100)
    # Resale is buyer-paid total before tax. Fees conservatively include estimated buyer sales tax.
    fee=resale*(1+s['buyer_tax']/100)*s['fee']/100+s['order_fee']
    proceeds=resale-fee-s['outbound']
    # Apply acquisition tax to bid plus purchase shipping (conservative assumption).
    factor=1+s['purchase_tax']/100; cost=(s['bid']+s['inbound'])*factor
    profit=proceeds-cost; roi=profit/cost*100 if cost>0 else None
    limit_profit=(proceeds-s['min_profit'])/factor-s['inbound']
    limit_roi=proceeds/(1+s['min_roi']/100)/factor-s['inbound']
    raw_limit=min(limit_profit,limit_roi); limit=floor_money(raw_limit)
    older=[D(r['price'])+D(r['shipping'] or 0) for r in recent if (now()-parse_date(r['date'])).days>=30]
    newer=[D(r['price'])+D(r['shipping'] or 0) for r in recent if (now()-parse_date(r['date'])).days<30]
    trend=(median(newer)/median(older)-1)*100 if len(older)>=3 and len(newer)>=3 else None
    limit_cost=(D(limit)+s['inbound'])*factor
    base.update(profit_at_max=money(proceeds-limit_cost),roi_at_max=money((proceeds-limit_cost)/limit_cost*100) if limit_cost>0 else None,cost_at_max=money(limit_cost),break_even_bid=floor_money(proceeds/factor-s['inbound']),trend_pct=money(trend) if trend is not None else None,median=money(med),estimate=money(resale),profit=money(profit),roi=money(roi) if roi is not None else None,max_bid=limit,net_proceeds=money(proceeds),acquisition_cost=money(cost))
    if source=='demo': base.update(recommendation='DEMO ONLY',reason='Synthetic prices — never use for real bidding.')
    elif age_hours(fetched)>24: base.update(recommendation='STALE — PASS',reason='Cache older than 24 hours. Refresh before relying on the bid limit.')
    elif last30<3: base.update(recommendation='LOW LIQUIDITY — PASS',reason='Fewer than three confirmed recent sales in the 30-day sample.')
    elif med>0 and (vals[-1]-vals[0])/med>D('.75'): base.update(recommendation='REVIEW — PASS',reason='Wide price spread; verify variants and sale conditions.')
    elif raw_limit<0 or s['bid']>D(str(limit)): base.update(recommendation='PASS',reason='Current bid exceeds your profit or ROI target.')
    else: base.update(recommendation='BUY CANDIDATE',reason='Within both targets, based on manually confirmed comps. Not a guarantee.')
    return base
