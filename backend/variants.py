"""One broad sales search, separated title-derived candidates, and user-verified slab memory."""
import re
from . import core

# Longest explicit phrases first. A title lacking a variant is NOT proof of Base.
# Color-only words are too ambiguous (team names, uniforms, label colors).
NAMES=('Gold Vinyl','Black Gold','Red White Blue','Red White and Blue','Pink Camo','Camo Pink','Reactive Orange','Reactive Blue','Reactive Green','Reactive Yellow','Red Ice','Blue Ice','Pink Ice','Cracked Ice','Black Ice','Silver Prizm','Mosaic Prizm','Silver Mosaic','Gold Mosaic','Green Mosaic','Red Mosaic','Blue Mosaic','Pink Mosaic','Purple Mosaic','Orange Mosaic','Fast Break','No Huddle','Tie Dye','Animal Print','Black Finite','Gold Wave','Green Wave','Red Wave','Blue Wave','Pink Wave','Purple Wave','Gold Refractor','Blue Refractor','Green Refractor','Red Refractor','Orange Refractor','Pink Refractor','Purple Refractor','Sepia Refractor','X-Fractor','Superfractor','Prizm Silver','Genesis','Peacock','Zebra','Tiger','Snakeskin','Checkerboard','Kaboom','Downtown','Color Blast','Stained Glass','Silver','Refractor','Holo','Hyper','Disco','Pulsar','Mojo','Scope','Shimmer','Sparkle','Velocity','Laser','Lazer','Atomic','Sapphire','Cosmic')

# Only unambiguous word-order aliases, not visually distinct finishes.
ALIASES={'prizm silver':'Silver Prizm','camo pink':'Pink Camo','red white and blue':'Red White Blue'}
def canonical(name):return ALIASES.get(core.norm(name),name)

def family_key(card):
    return 'family:v1:'+core.cache_key({k:v for k,v in card.items() if k!='variant' and v})

def group_name(item,card):
    title=str(item.get('title','')); t=core.norm(title)
    # Strip known identity, not card artwork or other arbitrary words.
    for k in ('year','player','set'):
        t=re.sub(r'\b'+re.escape(core.norm(card[k]))+r'\b',' ',t)
    # Sports team colors are not evidence of a parallel.
    for team in ('green bay packers','red sox','white sox','blue jays','golden state warriors','red wings','blue devils','red raiders','blackhawks'):
        t=re.sub(r'\b'+team+r'\b',' ',t)
    t=re.sub(r'\b(?:gold label|black label)\b',' ',t)
    # Unsupported inserts/serials/relics are not combined with standard cards.
    if re.search(core.SPECIAL,t) or re.search(r'(?<!\w)\d{0,5}/\d{1,5}\b',title): return None
    if re.search(r'\b(?:variation|short print|ssp|numbered|serial numbered|error|photo variation)\b',t):return None
    found=[];rest=t
    for name in sorted(NAMES,key=lambda x:len(core.norm(x)),reverse=True):
        pat=r'\b'+re.escape(core.norm(name))+r'\b'
        if re.search(pat,rest):
            found.append(name);rest=re.sub(pat,' ',rest)
    if len(found)>1:return None
    if re.search(core.PARALLELS,rest) or re.search(r'\b(?:prizm|insert|die cut|diecut|sp)\b',rest):return None
    meta=item.get('card') or {}
    flags=meta.get('flags') or [] if isinstance(meta,dict) else []
    if any('numbered' in str(f).lower() for f in flags):return None
    if found:
        if core.phrase(rest,'base'):return None
        return canonical(found[0])
    if any('parallel' in str(f).lower() for f in flags):return None
    return 'Base' if core.phrase(rest,'base') else 'Unspecified'

def groups(items,card):
    grouped={};seen=set()
    for item in items:
        if not isinstance(item,dict):continue
        row=core.candidate(item,dict(card,variant='Unknown'),identity_only=True)
        if not row or row['id'] in seen:continue
        seen.add(row['id']); name=group_name(item,card)
        if name is not None:grouped.setdefault(name,[]).append(row)
    return {name:sorted(rows,key=lambda r:r['date'],reverse=True) for name,rows in grouped.items()}

def exact_rows(items,card):
    # Reuse identity-screened groups; avoid known competing variants. Every row still needs review.
    variant=core.norm(canonical(card['variant'])); classified=groups(items,card)
    if variant=='base':allowed=classified.get('Base',[])+classified.get('Unspecified',[])
    else:allowed=[r for name,rows in classified.items() if core.norm(name)==variant for r in rows]
    return sorted(allowed,key=lambda r:r['date'],reverse=True)

def memory_key(grader,cert):return 'verified-slab:v1:'+grader+':'+cert

def recall(result):
    f=result['fields']; m=result.get('metadata',{}); cert=m.get('cert_number'); grader=f.get('grader')
    if not cert or not grader or not re.fullmatch(r'[A-Za-z0-9-]{5,32}',cert):return result
    old=core.get_cache(memory_key(grader,cert))
    if not old:return result
    saved=old[0]['card']; keys=('year','player','set','number','grader','grade','grade_type')
    if any(core.norm(f.get(k,''))!=core.norm(saved.get(k,'')) for k in keys):return result
    if f.get('variant') and core.norm(f['variant'])!=core.norm(saved['variant']):return result
    if m.get('autograph') is True or m.get('print_serial') or re.search(core.SPECIAL,core.norm(saved['variant'])):return result
    return dict(result,fields=dict(f,variant=saved['variant']),missing=[k for k in result['missing'] if k!='variant'],auto_eligible=True,remembered=True,warnings=[w for w in result['warnings'] if not w.startswith('Parallel not established')]+['Variant recalled from your previously confirmed certificate; check the physical slab.'])
