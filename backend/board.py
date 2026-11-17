"""A single mixed-grade search; title-derived reference cells, never automated buy signals."""
import re
from collections import defaultdict
from statistics import median
from decimal import Decimal as D
from . import core, variants

GRADES=['Raw']+[f'PSA {n}' for n in range(1,11)]
GRADER_RE=r'\b(?:psa|bgs|sgc|cgc|tag|beckett|ace|hga|graded|slabbed)\b'

def key(card):
    return 'board:v1:'+core.cache_key({k:card.get(k,'') for k in ('player','year','set','number')})

def grade_for(item):
    t=core.norm(item.get('title','')); m=item.get('card') or {}
    if not isinstance(m,dict):m={}
    g=core.norm(m.get('grader') or '').upper(); d=str(m.get('grade') or '').removesuffix('.0')
    if g=='BECKETT':g='BGS'
    # Raw grading candidates / ambiguous descriptions do not enter price cells.
    if re.search(r'\b(?:contender|candidate|potential|ready to grade|not graded|not psa)\b',t):return None
    if g or d or m.get('graded') is True:
        if g not in ('PSA','BGS','CGC','SGC') or not re.fullmatch(r'(?:[1-9](?:\.5)?|10)',d):return None
    else:
        title=str(item.get('title',''))
        hit=re.search(r'\b(PSA|BGS|CGC|SGC)\s*(?:(?:GEM\s*(?:MT|MINT)|PRISTINE|PERFECT|BLACK LABEL)\s*)?(10|[1-9](?:\.5)?)(?![\d.])',title,re.I)
        if hit:
            if m.get('graded') is False:return None
            g,d=hit.group(1).upper(),hit.group(2)
        elif re.search(GRADER_RE,t):return None
        else:return ('RAW','','','Raw')
    explicit=re.findall(r'\b(PSA|BGS|CGC|SGC)\s*(?:(?:GEM\s*(?:MT|MINT)|PRISTINE|PERFECT|BLACK LABEL)\s*)?(10|[1-9](?:\.5)?)(?![\d.])',str(item.get('title','')),re.I)
    if any((a.upper(),b)!=(g,d) for a,b in explicit):return None
    gt=''
    if g!='PSA' and d=='10':
        found=[v for v in ('Pristine','Gem Mint','Perfect','Black Label') if core.phrase(t,v)]
        if found==['Pristine','Black Label']:found=['Black Label']
        if len(found)!=1:return None
        gt=found[0]
    return (g,d,gt,' '.join(x for x in (g,gt,d) if x))

def number_for(item):
    meta=item.get('card') or {}; meta=meta if isinstance(meta,dict) else {}
    n=str(meta.get('card_number') or '').strip().lstrip('#')
    if not n:
        hit=re.search(r'(?:#\s*|\bno\.?\s+|\bcard\s+#\s*)([A-Za-z0-9-]{1,20})(?![\w/-])',str(item.get('title','')),re.I)
        n=hit.group(1) if hit else ''
    if not re.fullmatch(r'[A-Za-z0-9-]{1,20}',n) or core.norm(n) in ('rc','rookie','na') or not any(c.isdigit() for c in n):return ''
    return n.upper()

def clean_season(title):
    return re.sub(r'\b((?:19|20)\d{2})/(\d{2}|(?:19|20)\d{2})\b',r'\1-\2',title)

def reference_limit(rows,settings,fetched):
    """Low-confidence reference only, not a verified bid. Never mix grades or variants."""
    if not rows or core.age_hours(fetched)>24:return None
    # Treat unknown shipping as zero revenue. Use the lowest observed sale for sparse samples.
    vals=sorted(D(str(r['price']))+D(str(r['shipping'] or 0)) for r in rows)
    s={k:D(str(v)) for k,v in settings.items()}
    if len(vals)<5: anchor=vals[0]; extra=D('.20')
    else:
        pos=D(len(vals)-1)*D('.25'); i=int(pos)
        anchor=vals[i]+(vals[min(i+1,len(vals)-1)]-vals[i])*(pos-i);extra=D('.15')
    resale=anchor*(1-s['haircut']/100)*(1-extra)
    proceeds=resale-resale*(1+s['buyer_tax']/100)*s['fee']/100-s['order_fee']-s['outbound']
    factor=1+s['purchase_tax']/100
    limit=core.floor_money(min((proceeds-s['min_profit'])/factor-s['inbound'],proceeds/(1+s['min_roi']/100)/factor-s['inbound']))
    cost=(D(str(limit))+s['inbound'])*factor
    return {'bid':limit,'profit':core.money(proceeds-cost) if limit>0 else None,'roi':core.money((proceeds-cost)/cost*100) if limit>0 and cost>0 else None}

def build(items,card,settings,fetched):
    buckets=defaultdict(list); unresolved=[]; seen=set()
    for item in items:
        if not isinstance(item,dict):continue
        title=str(item.get('title','')); t=core.norm(title)
        if not core.phrase(t,card['player']) or re.search(core.JUNK,t):continue
        if any(card.get(k) and not core.phrase(t,card[k]) for k in ('year','set')):continue
        grade=grade_for(item)
        if not grade:continue
        number=number_for(item)
        if card.get('number') and core.norm(number)!=core.norm(card['number']):continue
        # Missing year/product/number cannot identify a family safely. Show individual references only.
        g,d,gt,grade_label=grade
        fixed=dict(item,title=clean_season(title)); edition=re.sub(r'\b'+re.escape(core.norm(card.get('set','')))+r'\b',' ',core.norm(fixed['title'])) if card.get('set') else core.norm(fixed['title'])
        special=bool(re.search(core.SPECIAL,edition)); runs=re.findall(r'(?<![\w/])(?:\d{1,6})?\s*/\s*(\d{1,6})\b',fixed['title'])
        run=str(int(runs[0])) if runs and len(set(runs))==1 and int(runs[0])>0 else ''
        if card.get('year') and card.get('set'):
            identity=dict(card,number=number,grader=g,grade=d,grade_type=gt,variant='Unknown')
            if special:identity['variant']=' '.join(x for x,p in [('Autograph',r'\b(?:auto|autograph|autographed)\b'),('Relic',r'\b(?:patch|relic)\b')] if re.search(p,edition))
            if run:identity['print_run']=run
            row=core.candidate(fixed,identity,identity_only=True)
        else:
            # Avoid aggregating unknown products. Validate sale fundamentals only.
            try:
                price=float(item['price']); ship=item.get('shipping_cost');ship=float(ship) if ship is not None else None;dt=core.parse_date(item.get('last_sold'))
                import math
                if not dt or dt>core.now() or not math.isfinite(price) or price<=0 or (ship is not None and (not math.isfinite(ship) or ship<0)):continue
                row={'id':str(item.get('item_id') or ''),'title':title[:500],'price':price,'shipping':ship,'date':dt.isoformat(),'url':str(item.get('url') or '')}
            except (ValueError,TypeError,KeyError):continue
        if not row or not row['id'] or row['id'] in seen or (core.now()-core.parse_date(row['date'])).days>=90:continue
        seen.add(row['id']);row['title']=title[:500]
        name=variants.group_name(fixed,identity) if card.get('year') and card.get('set') and not (special or runs) else None
        if not number or not name or not card.get('year') or not card.get('set'):
            unresolved.append(dict(row,grade_label=grade_label));continue
        buckets[(number,name,grade_label)].append(row)
    groups={}
    for (number,name,grade),rows in buckets.items():
        rows.sort(key=lambda r:r['date'],reverse=True)
        calc=core.calculate(rows,dict(settings,bid=0),fetched,'compsapi')
        # Sparse cells may display observed sold median, never a bid. Unknown shipping makes an estimate unsafe.
        known=[r for r in rows if r['shipping'] is not None]
        value=round(median([r['price']+r['shipping'] for r in known]),2) if known else None
        usable=(len(known)==len(rows) and calc['recommendation']=='BUY CANDIDATE' and calc['max_bid'] is not None and calc['max_bid']>0)
        # Unspecified is deliberately a different row from Base. Bid is explicitly conditional.
        cell={'grade':grade,'count':len(rows),'known_shipping':len(known),'last30':calc['last30_sample'],'median':value,'item_median':round(median([r['price'] for r in rows]),2),'max_bid':calc['max_bid'] if usable else None,'reason':('Recent title-derived sales meet the configured profit and ROI targets; identity and comps remain unverified.' if usable else ('Insufficient margin at a positive bid.' if calc['recommendation']=='BUY CANDIDATE' else calc['reason'])) if len(known)==len(rows) else 'Some shipping costs unknown; no bid estimate.','sales':rows[:12]}
        # Unspecified titles may contain mixed variants; no actionable reference ceiling for those.
        ref=None if name=='Unspecified' or usable else reference_limit(rows,settings,fetched)
        if name=='Unspecified':cell['max_bid']=None
        cell['reference_bid']=ref['bid'] if ref else None
        cell['reference_profit']=ref['profit'] if ref else None
        cell['reference_roi']=ref['roi'] if ref else None
        cell['profit_at_max']=calc.get('profit_at_max') if cell['max_bid'] is not None else None
        cell['roi_at_max']=calc.get('roi_at_max') if cell['max_bid'] is not None else None
        groups.setdefault((number,name),{})[grade]=cell
    data=[{'number':n,'variant':v,'cells':cells} for (n,v),cells in groups.items()]
    data.sort(key=lambda x:(x['number'],x['variant'] not in ('Base','Unspecified'),x['variant']))
    unresolved.sort(key=lambda r:r['date'],reverse=True)
    return {'groups':data,'unresolved':unresolved[:40],'unresolved_count':len(unresolved),'grades':GRADES,'matched_count':len(seen)}
