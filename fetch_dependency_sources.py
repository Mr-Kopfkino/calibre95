"""Fetch source archives from DEPENDENCY_SOURCES.json; never execute them.

python fetch_dependency_sources.py --manifest DEPENDENCY_SOURCES.json --output sources
Use --all to fetch every dependency; default fetches entries not locally mirrored.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--manifest',type=Path,default=Path(__file__).with_name('DEPENDENCY_SOURCES.json'))
parser.add_argument('--output',type=Path,default=Path('dependency-sources'))
parser.add_argument('--all',action='store_true')
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
records=json.loads(args.manifest.read_text(encoding='utf-8'))['components']
failed=[]
def digest_file(path,algorithm):
    digest=hashlib.new(algorithm)
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    return digest.hexdigest()
for row in records:
    if row['status']=='mirrored' and not args.all:continue
    filename=row['filename']
    if Path(filename).name!=filename:raise ValueError('unsafe filename')
    destination=args.output/filename
    algorithm,expected=row['declared_digest'].split(':',1)
    if destination.is_file() and digest_file(destination,algorithm)==expected:
        print('verified existing',filename);continue
    urls=list(row['upstream_urls'])
    if row.get('pypi_metadata_url'):
        with urllib.request.urlopen(row['pypi_metadata_url'],timeout=60) as response:
            data=json.load(response)
        urls[:0]=[f['url'] for f in data['urls'] if f.get('digests',{}).get(algorithm)==expected]
    errors=[]
    for url in urls:
        try:
            temp=destination.with_name(filename+'.download')
            digest=hashlib.new(algorithm)
            with urllib.request.urlopen(url,timeout=90) as response,temp.open('wb') as stream:
                while block:=response.read(64*1024):digest.update(block);stream.write(block)
            if digest.hexdigest()!=expected:raise ValueError('digest mismatch')
            temp.replace(destination)
            print('verified',filename)
            break
        except Exception as error:errors.append(str(error))
    else:failed.append((filename,errors))
if failed:raise SystemExit('Downloads incomplete: '+repr(failed))
