import json, re, csv, io, zipfile
from datetime import datetime

print("US MARKET SNAPSHOT —", datetime.now().strftime("%Y-%m-%d %H:%m"), "\n")

def val(v): return v if v not in ('.', '') else 'NA'

# FRED rates
with zipfile.ZipFile('/tmp/us_mkt/fred_rates.csv') as z:
    inner = [n for n in z.namelist() if n.endswith('.csv')][0]
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(inner), encoding='utf-8-sig')))
print("[FRED rates] last rows:")
for r in rows[-4:]:
    print(f"  {r['observation_date']}  2Y {val(r['DGS2']):>5}  10Y {val(r['DGS10']):>5}  30Y {val(r['DGS30']):>5}  10Y2Y {val(r['T10Y2Y'])}")

# credit
rows2 = list(csv.DictReader(open('/tmp/us_mkt/fred_credit.csv')))
print("\n[Credit] last rows:")
for r in rows2[-3:]:
    print(f"  {r['observation_date']}  HY {val(r['BAMLH0A0HYM2']):>6}  IG {val(r['BAMLC0A0CM']):>6}")

# macro: mom calc
rows3 = list(csv.DictReader(open('/tmp/us_mkt/fred_macro.csv')))
print("\n[Macro] last 4:")
for i, r in enumerate(rows3[-4:]):
    idx = len(rows3) - 4 + i
    line = f"  {r['observation_date']}  CPI {r['CPIAUCSL']}  CorePCE {r['PCEPILFE']}  U3 {r['UNRATE']}  Pay {r['PAYEMS']}"
    if idx > 0:
        p = rows3[idx-1]
        try:
            cpi = (float(r['CPIAUCSL'])/float(p['CPIAUCSL'])-1)*100
            pce = (float(r['PCEPILFE'])/float(p['PCEPILFE'])-1)*100
            pay = float(r['PAYEMS'])-float(p['PAYEMS'])
            line += f"  | MoM: CPI {cpi:+.2f}% PCE {pce:+.2f}% PayΔ{pay:+.0f}k"
        except: pass
    print(line)

# yahoo
def yh(path, label):
    d = json.load(open(path)); r = d['chart']['result'][0]
    ts = r['timestamp']; cl = r['indicators']['quote'][0]['close']
    pts = [(t,c) for t,c in zip(ts,cl) if c]
    lt, lc = pts[-1]
    jan1 = datetime(2026,1,1).timestamp()
    base = [c for t,c in pts if t < jan1][-1]
    ytd = (lc/base-1)*100
    hi, lo = max(c for _,c in pts), min(c for _,c in pts)
    ma50 = [c for _,c in pts][-50]; ma200 = [c for _,c in pts][-200:]
    m_ago = lt - 30*86400
    pm = [c for t,c in pts if t < m_ago][-1]
    off_hi = (lc/hi-1)*100
    print(f"  {label:7s} {lc:>9.2f}  YTD {ytd:+6.2f}%  1M {(lc/pm-1)*100:+5.2f}%  off52wH {off_hi:+5.1f}%  MA50 {'↑' if lc>ma50 else '↓'} MA200 {'↑' if lc>sum(ma200)/len(ma200) else '↓'}  ({datetime.fromtimestamp(lt).strftime('%m-%d')})")

print("\n[Yahoo returns]")
for f, lab in [('yh_gspc.json','S&P500'), ('yh_ixic.json','NASDAQ'), ('yh_dji.json','DOW'), ('yh_rut.json','RUT2000'), ('yh_gold.json','GOLD')]:
    try: yh(f'/tmp/us_mkt/{f}', lab)
    except Exception as e: print(f'  {lab} FAIL {e}')

# treasury XML: latest curve
print("\n[Treasury curve — latest]")
import xml.etree.ElementTree as ET
tree = ET.parse('/tmp/us_mkt/treasury_2026.xml')
ents = []
for e in tree.iter():
    if e.tag.endswith('NEW_DATE'):
        ents.append(e)
props = tree.getroot().iter()
# simpler: collect all properties
curves = {}
for p in tree.iter():
    if p.tag.endswith('}properties') or p.tag == 'properties':
        d = {}
        for c in p.iter():
            tag = c.tag.split('}')[-1]
            if tag.startswith('BC_') and c.text:
                d[tag[3:]] = c.text
            if tag == 'NEW_DATE' and c.text:
                d['date'] = c.text[:10]
        if d.get('date'): curves[d['date']] = d
latest = curves[max(curves)]
print(f"  {latest['date']}: " + "  ".join(f"{k} {v}" for k, v in sorted(latest.items()) if k != 'date'))
# curve 1m ago
import datetime as dt
dates = sorted(curves)
d1m = [x for x in dates if x <= '2026-07-20'][-1]
print(f"  {d1m}: " + "  ".join(f"{k} {curves[d1m][k]}" for k in ['1Mo','3Mo','6Mo','1Yr','2Yr','3Yr','5Yr','7Yr','10Yr','20Yr','30Yr'] if k in curves[d1m]))
dstart = [x for x in dates if x <= '2026-01-05'][-1]
print(f"  {dstart} (YTD base): " + "  ".join(f"{k} {curves[dstart][k]}" for k in ['2Yr','5Yr','10Yr','30Yr'] if k in curves[dstart]))
