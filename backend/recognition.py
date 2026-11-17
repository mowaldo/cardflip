"""Conservative local multi-grader label parsing. Never assume an unlabeled card is Base."""
import re
from .core import norm, PARALLELS

# Small initial catalog, not an exhaustive card database. Unknown products require manual entry.
SETS = ('Panini Prizm Draft Picks','Panini Donruss Optic','Panini Select','Panini Prizm','Panini Mosaic','Panini Donruss','Panini Hoops','Panini Chronicles','Panini Contenders','Panini Revolution','Topps Chrome Update','Topps Chrome','Bowman Chrome','Topps Update','Topps Finest','Topps Now','Topps','Bowman')
VARIANTS = ('Red White Blue','Red Ice','Blue Ice','Cracked Ice','Silver Prizm','Silver','Green Prizm','Green','Gold Prizm','Gold','Hyper','Fast Break','Pink Ice','Orange Ice','Purple','Blue','Red','Refractor','Base')

def parse_label(text):
    lines=[re.sub(r'\s+',' ',s).strip().strip('|_¦').strip() for s in text.splitlines() if s.strip()]
    full='\n'.join(lines); result={}; warnings=[]
    years=set(re.findall(r'(?<!\d)(?:19\d{2}|20\d{2})(?!\d)',full))
    # A date on a certification line or a second year is ambiguous; no guess.
    if len(years)==1: result['year']=years.pop()
    numbers=set(re.findall(r'(?:#\s*|\bNO\.?\s+)([A-Z0-9][A-Z0-9-]{0,19})(?![\w/])',full,re.I))
    if len(numbers)==1: result['number']=numbers.pop().upper()
    set_hits=[]
    for line in lines:
        for name in SETS:
            if f' {norm(name)} ' in f' {norm(line)} ':
                set_hits.append((name,line));break
    if len({x[0] for x in set_hits})==1:
        result['set']=set_hits[0][0]
    graders=set()
    for grader, pattern in {
        'PSA':r'\b(?:PSA|professional sports authenticator)\b',
        'CGC':r'\b(?:CGC|certified guaranty company)\b',
        'BGS':r'\b(?:BGS|Beckett grading services|Beckett)\b',
        'SGC':r'\b(?:SGC|sportscard guaranty)\b',
    }.items():
        if re.search(pattern,full,re.I): graders.add(grader)
    # PSA's abbreviated grade terminology is a fallback only if no other grader is recognized.
    if not graders and re.search(r'\bGEM\s*MT\b|\bNM\s*-?\s*MT\b',full,re.I): graders.add('PSA')
    grades=set(re.findall(r'\b(?:GEM\s*(?:MT|MINT)|MINT|NM\s*-?\s*MT|PRISTINE|PERFECT|BLACK\s+LABEL|PSA|CGC|BGS|SGC)\s*(10|[1-9](?:\.5)?)(?![\d.])',full,re.I))
    grades.update(re.findall(r'(?<![\d.])(10|[1-9](?:\.5)?)\s+(?:GEM\s*(?:MT|MINT)|PRISTINE|PERFECT|BLACK\s+LABEL)\b',full,re.I))
    if len(graders)==1:
        result['grader']=next(iter(graders))
        if len(grades)==1: result['grade']=next(iter(grades))
    if result.get('grade')=='10' and result.get('grader') in ('CGC','BGS','SGC'):
        types=set()
        for label,pattern in [('Pristine',r'\bPRISTINE\b'),('Gem Mint',r'\bGEM\s*(?:MT|MINT)\b'),('Perfect',r'\bPERFECT\b'),('Black Label',r'\bBLACK\s+LABEL\b')]:
            if re.search(pattern,full,re.I):types.add(label)
        # Beckett Black Label is a distinct grade designation, often also called pristine.
        if result['grader']=='BGS' and 'Black Label' in types:types.discard('Pristine')
        if len(types)==1:result['grade_type']=next(iter(types))
        else:warnings.append('Confirm the exact 10 grade designation (Pristine, Gem Mint, etc.).')
    # PSA labels commonly have a standalone player line. Reject ambiguous candidate lines.
    candidates=[]
    for index,line in enumerate(lines):
        if any(line==s[1] for s in set_hits):continue
        if re.search(r'\d|\b(?:PSA|CGC|BGS|SGC|BECKETT|CERTIFIED|GUARANTY|COMPANY|PRISTINE|PERFECT|GEM|MINT|CERT|ROOKIE|PRIZM|PANINI|TOPPS|BOWMAN|AUTHENTIC|AUTO|AUTOGRAPH)\b',line,re.I):continue
        if re.search(PARALLELS,norm(line)) or any(norm(line)==norm(v) for v in VARIANTS):continue
        if re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ.'’\-]+(?: [A-Za-zÀ-ÖØ-öø-ÿ.'’\-]+){1,4}",line):candidates.append((index,line))
    if 'set' in result and 'year' in result:
        names={norm(line):line for _,line in candidates}
        if len(names)==1:
            result['player']=next(iter(names.values())).title()
        elif len(names)>1:
            # PSA identity is normally printed immediately under the year/product.
            # Prefer that uppercase line over mixed-case OCR debris only; do not
            # choose between multiple plausible uppercase or title-case names.
            anchors={i for i,line in enumerate(lines) if any(line==hit[1] for hit in set_hits) and result['year'] in line}
            adjacent=[(i,line) for i,line in candidates if i-1 in anchors and line.isupper()]
            if len(adjacent)==1:
                idx,name=adjacent[0]
                other=[line for i,line in candidates if i!=idx and norm(line)!=norm(name)]
                if all(not line.isupper() and not line.istitle() for line in other):
                    result['player']=name.title()
                    warnings.append('Player selected from the PSA identity line; ignored mixed-case OCR noise. Verify the name.')
    # CGC and other graders often print the card number and player on the same line.
    # Extract only from a labeled number followed by a name, not arbitrary artwork text.
    if 'set' in result and 'year' in result and 'number' in result and 'player' not in result:
        names=set()
        for line in lines:
            m=re.match(r'^(?:#\s*|NO\.?\s+)'+re.escape(result['number'])+r'\s+([A-Za-zÀ-ÖØ-öø-ÿ.‘’\-]+(?: [A-Za-zÀ-ÖØ-öø-ÿ.‘’\-]+){1,4})$',line,re.I)
            if m and not re.search(r'\b(?:PSA|CGC|BGS|SGC|GEM|MINT|PRISTINE|ROOKIE|AUTO|CERT)\b',m.group(1),re.I): names.add(m.group(1).title())
        if len(names)==1: result['player']=names.pop()
    # Only accept explicit standalone variant or a trailing label line, never infer Base from absence.
    variants=set()
    for line in lines:
        for name in VARIANTS:
            if norm(line)==norm(name):variants.add(name);break
    if len(variants)==1:result['variant']=variants.pop()
    if re.search(r'\b(?:AUTO|AUTOGRAPH|PATCH|RELIC)\b|\d+/\d+',full,re.I):
        result.pop('variant',None);warnings.append('Special or numbered card: confirm exact variant manually.')
    if 'variant' not in result:warnings.append('Variant not explicit. Inspect the card; enter Base only if confirmed.')
    missing=[key for key in ('year','player','set','number','variant','grader','grade') if key not in result]
    if result.get('grader') in ('CGC','BGS','SGC') and result.get('grade')=='10' and 'grade_type' not in result:missing.append('grade_type')
    return {'fields':result,'missing':missing,'warnings':warnings,'text':text[:4000]}
