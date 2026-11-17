"""Explicit single certificate access check. Never prints tokens or contacts PSA on startup."""
import argparse, os, re, sys, json
from pathlib import Path
import requests
from dotenv import load_dotenv

def main():
    p=argparse.ArgumentParser();p.add_argument('cert');args=p.parse_args()
    if not re.fullmatch(r'\d{5,12}',args.cert):p.error('Provide a numeric PSA certificate number.')
    load_dotenv(Path(__file__).resolve().parent/'.env'); token=os.getenv('PSA_API_TOKEN','').strip()
    if not token:sys.exit('PSA_API_TOKEN missing from .env.')
    try:
        r=requests.get('https://api.psacard.com/publicapi/cert/GetByCertNumber/'+args.cert,headers={'Authorization':'Bearer '+token,'Accept':'application/json'},timeout=(5,25),allow_redirects=False)
    except requests.exceptions.ConnectTimeout:sys.exit('PSA connection timed out before an HTTP response. Access not established.')
    except requests.exceptions.ReadTimeout:sys.exit('PSA response timed out. Access not established; no automatic retry.')
    except requests.exceptions.SSLError:sys.exit('PSA TLS certificate verification failed. Check system trust/date; do not disable TLS verification.')
    except requests.exceptions.ConnectionError:sys.exit('PSA connection failed (DNS, network or server unreachable). No HTTP response received.')
    except requests.RequestException as e:sys.exit('PSA request failed ('+type(e).__name__+'). Access not established.')
    print('HTTP',r.status_code)
    try:data=r.json()
    except ValueError:sys.exit('PSA returned non-JSON content. HTTP status above; access not established.')
    if not isinstance(data,dict):sys.exit('Unexpected PSA response.')
    # Do not print unrecognized payloads or headers; show only documented record fields.
    if 'approved customers' in str(data.get('Message','')).lower():sys.exit('PSA account requires approval. Contact PSA support; token alone is not sufficient.')
    if r.status_code in (401,403):sys.exit('PSA rejected access (HTTP '+str(r.status_code)+'). Check token and account approval.')
    if r.status_code!=200 or data.get('IsValidRequest') is not True or str(data.get('ServerMessage','')).lower()!='request successful':sys.exit('Certificate not returned. Check approval, token and certificate.')
    record=data.get('PSACert') or {}
    if not isinstance(record,dict):sys.exit('No structured PSA certificate record returned.')
    print(json.dumps({k:record[k] for k in ('CertNumber','SpecID','SpecNumber','Year','Brand','Category','CardNumber','Subject','Variety','CardGrade','TotalPopulation','PopulationHigher','GradeDescription') if k in record},indent=2))
if __name__=='__main__':main()
