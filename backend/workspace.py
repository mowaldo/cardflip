"""Local history, explicitly recorded inventory and chronological paper research."""
import json, uuid, math
from decimal import Decimal as D, ROUND_HALF_UP
from datetime import timedelta
from statistics import median
from . import core

def cents(v):return int((D(str(v))*100).quantize(D('1'),rounding=ROUND_HALF_UP))
def dollars(v):return None if v is None else v/100

def tables(c):
    c.execute('CREATE TABLE IF NOT EXISTS scan_history (id TEXT PRIMARY KEY, card TEXT NOT NULL, seen TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS inventory (id TEXT PRIMARY KEY, card TEXT NOT NULL, mode TEXT NOT NULL, acquired TEXT NOT NULL, paid INTEGER NOT NULL, inbound INTEGER NOT NULL, tax INTEGER NOT NULL, snapshot INTEGER, snapshot_at TEXT, note TEXT NOT NULL, sold TEXT, gross INTEGER, selling INTEGER, outbound INTEGER, other INTEGER, strategy TEXT NOT NULL)')

def record(card,kind,detail=None):
    card={k:str(card.get(k) or '')[:80] for k in ('player','year','set','number','variant','grader','grade','grade_type','print_run')}
    if not core.norm(card['player']):return
    key=core.cache_key({k:card[k] for k in ('player','year','set','number')})
    with core.connection() as c:
        tables(c);old=c.execute('SELECT card FROM scan_history WHERE id=?',(key,)).fetchone()
        if old and kind=='price board':
            prev=json.loads(old['card']);card={k:v or prev.get(k,'') for k,v in card.items()}
        c.execute('INSERT OR REPLACE INTO scan_history VALUES (?,?,?,?,?)',(key,json.dumps(card),core.stamp(),kind,json.dumps(detail or {})))
        c.execute('DELETE FROM scan_history WHERE id IN (SELECT id FROM scan_history ORDER BY seen DESC LIMIT -1 OFFSET 200)')

def history():
    with core.connection() as c:
        tables(c);return [dict(id=r['id'],card=json.loads(r['card']),seen=r['seen'],kind=r['kind'],detail=json.loads(r['detail'])) for r in c.execute('SELECT * FROM scan_history ORDER BY seen DESC')]

def clear_history():
    with core.connection() as c:
        tables(c);return c.execute('DELETE FROM scan_history').rowcount

def create(entry):
    i=uuid.uuid4().hex
    with core.connection() as c:
        tables(c);c.execute('INSERT INTO inventory (id,card,mode,acquired,paid,inbound,tax,snapshot,snapshot_at,note,strategy) VALUES (?,?,?,?,?,?,?,?,?,?,?)',(i,json.dumps(entry['card']),entry['mode'],core.stamp(),cents(entry['paid']),cents(entry['inbound']),cents(entry['tax']),None if entry['net_value'] is None else cents(entry['net_value']),core.stamp() if entry['net_value'] is not None else None,entry['note'],entry['strategy']))
    return i

def update(i,net_value):
    with core.connection() as c:
        tables(c);return c.execute('UPDATE inventory SET snapshot=?, snapshot_at=? WHERE id=? AND sold IS NULL',(None if net_value is None else cents(net_value),core.stamp() if net_value is not None else None,i)).rowcount==1

def sell(i,entry):
    with core.connection() as c:
        tables(c);return c.execute('UPDATE inventory SET sold=?,gross=?,selling=?,outbound=?,other=? WHERE id=? AND sold IS NULL',(core.stamp(),*[cents(entry[k]) for k in ('gross','selling','outbound','other')],i)).rowcount==1

def delete(i):
    with core.connection() as c:
        tables(c);return c.execute('DELETE FROM inventory WHERE id=?',(i,)).rowcount==1

def inventory(mode):
    with core.connection() as c:
        tables(c);rows=list(c.execute('SELECT * FROM inventory WHERE mode=? ORDER BY acquired DESC',(mode,)))
    result=[];cost_open=priced_cost=net_open=realized=sold_cost=0;owned=closed=priced=0
    for r in rows:
        cost=r['paid']+r['inbound']+r['tax'];profit=None;net=None
        if r['sold']:
            net=r['gross']-r['selling']-r['outbound']-r['other'];profit=net-cost;realized+=profit;sold_cost+=cost;closed+=1
        else:
            cost_open+=cost;owned+=1
            if r['snapshot'] is not None:priced+=1;priced_cost+=cost;net_open+=r['snapshot']
        result.append(dict(id=r['id'],card=json.loads(r['card']),mode=r['mode'],acquired=r['acquired'],sold=r['sold'],paid=dollars(r['paid']),inbound=dollars(r['inbound']),tax=dollars(r['tax']),cost=dollars(cost),net_value=dollars(r['snapshot']),snapshot_at=r['snapshot_at'],gross=dollars(r['gross']),selling=dollars(r['selling']),outbound=dollars(r['outbound']),other=dollars(r['other']),net=dollars(net),profit=dollars(profit),roi=round(profit/cost*100,2) if profit is not None and cost else None,note=r['note'],strategy=r['strategy']))
    return {'rows':result,'summary':{'owned':owned,'closed':closed,'priced':priced,'open_cost':dollars(cost_open),'net_value':dollars(net_open) if priced else None,'unrealized':dollars(net_open-priced_cost) if priced else None,'realized':dollars(realized),'realized_roi':round(realized/sold_cost*100,2) if sold_cost else None}}

def replay(rows,settings,days):
    """Strictly earlier sales form entry signal; subsequent observed sale is hypothetical exit."""
    rows=sorted([r for r in rows if r.get('shipping') is not None and core.parse_date(r.get('date'))],key=lambda r:r['date'])
    s={k:D(str(v)) for k,v in settings.items()}; trades=[]; tested=0; pending=0; last_exit=None
    def gross(r):return D(str(r['price']))+D(str(r['shipping']))
    def net(v):return v*(1-s['fee']/100*(1+s['buyer_tax']/100))-s['order_fee']-s['outbound']
    for i,r in enumerate(rows):
        dt=core.parse_date(r['date']); day=dt.date()
        if last_exit and day<=last_exit:continue
        prior=[p for p in rows[:i] if core.parse_date(p['date']).date()<day and dt-core.parse_date(p['date'])<=timedelta(days=90)]
        if len(prior)<5 or sum(dt-core.parse_date(p['date'])<=timedelta(days=30) for p in prior)<3:continue
        vals=sorted(gross(p) for p in prior);med=median(vals)
        if (vals[-1]-vals[0])/med>D('.75'):continue
        tested+=1;pos=D(len(vals)-1)/4;j=int(pos);q=vals[j]+(vals[min(j+1,len(vals)-1)]-vals[j])*(pos-j);proceeds=net(q*(1-s['haircut']/100));cost=gross(r)*(1+s['purchase_tax']/100)
        if cost<=0 or proceeds-cost<s['min_profit'] or (proceeds-cost)/cost*100<s['min_roi']:continue
        exit=next((p for p in rows[i+1:] if core.parse_date(p['date']).date()>=day+timedelta(days=days)),None)
        if not exit:pending+=1;break
        exitday=core.parse_date(exit['date']).date();actual=net(gross(exit));profit=actual-cost
        trades.append({'entry_date':str(day),'exit_date':str(exitday),'cost':core.money(cost),'net_exit':core.money(actual),'profit':core.money(profit),'roi':core.money(profit/cost*100),'entry_title':r['title'][:200],'exit_title':exit['title'][:200]});last_exit=exitday
    total=sum(t['profit'] for t in trades);capital=sum(t['cost'] for t in trades)
    return {'sales':len(rows),'tested':tested,'closed':len(trades),'pending':pending,'profit':round(total,2),'roi':round(total/capital*100,2) if capital else None,'wins':sum(t['profit']>0 for t in trades),'trades':trades,'note':'Historical title-derived sales; hypothetical fills at observed prices, one position at a time. Not actual auction executions or a forecast.'}

def assessment(cell,row,stale,identity):
    if stale or not identity or row['variant']=='Unspecified' or cell['count']<5 or cell['known_shipping']!=cell['count']:
        return {'label':'Research only','signals':['Sparse, stale or uncertain comparables.']}
    signals=[];trend=cell.get('trend_pct');recent=cell['last30']
    if recent<3:signals.append('Thin recent sales sample')
    if trend is not None:signals.append(f'Observed 90d trend {trend:+.1f}%')
    else:signals.append('Price trend unavailable')
    if cell.get('max_bid') is not None:signals.append('Conditional flip limit available')
    else:signals.append('No standard flip limit')
    return {'label':'Review for hold' if recent>=3 and trend is not None and trend>=0 else 'Caution / research','signals':signals,'note':'No projected return; player outlook and scarcity need independent review.'}
