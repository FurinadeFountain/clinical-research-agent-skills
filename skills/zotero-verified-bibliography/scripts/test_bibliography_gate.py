import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import bibliography_gate as gate

class GateTests(unittest.TestCase):
    def fixture(self):
        fields={'itemType':'journalArticle','title':'A test article','creators':[{'creatorType':'author','firstName':'Inéz','lastName':'Frerichs'}],'date':'2023','DOI':'10.example/a','publicationTitle':'Example Journal','volume':'20','issue':'11','pages':'770-783'}
        record={'ref':'a','key':'ABCDEFGH','expected':fields,'evidence':[{'source':'fixture:independent-expected','fields':list(fields)}]}
        manifest={'library':{'type':'user','id':123},'records':[record]}
        actual=[{'key':'ABCDEFGH','library':{'type':'user','id':123},'data':copy.deepcopy(fields),'bib':'<div>1. Frerichs I. A test article. Example J. 2023;20(11):770–83.</div>'}]
        return manifest,actual
    def test_actual_page_shift_fails(self):
        m,a=self.fixture();a[0]['data']['pages']='771-783'
        self.assertEqual(gate.compare(m,a)[0]['field'],'pages')
    def test_missing_volume_issue_pages_fails(self):
        m,a=self.fixture()
        for f in ('volume','issue','pages'):a[0]['data'].pop(f)
        self.assertEqual({x['field'] for x in gate.compare(m,a)}, {'volume','issue','pages'})
    def test_author_order_and_spelling(self):
        m,a=self.fixture();a[0]['data']['creators'][0]['firstName']='Iz'
        self.assertEqual(gate.compare(m,a)[0]['field'],'creators')
        m,a=self.fixture();second={'creatorType':'author','firstName':'Jane','lastName':'Smith'}
        m['records'][0]['expected']['creators'].append(second);a[0]['data']['creators'].insert(0,second)
        self.assertEqual(gate.compare(m,a)[0]['field'],'creators')
    def test_safe_normalization(self):
        m,a=self.fixture();a[0]['data']['DOI']='https://doi.org/10.EXAMPLE/A';a[0]['data']['pages']='770–783'
        self.assertEqual(gate.compare(m,a),[])
    def test_source_and_empty_field_gate(self):
        m,a=self.fixture();m['records'][0]['evidence']=[]
        self.assertTrue(gate.validate_manifest(m))
        m,a=self.fixture();m['records'][0]['expected']['pages']=''
        self.assertTrue(gate.validate_manifest(m))
        m['records'][0]['allowed_missing']={'pages':'Publisher explicitly has not assigned pages.'}
        self.assertEqual(gate.validate_manifest(m),[])
    def test_wrong_library_and_extra_item_fail(self):
        m,a=self.fixture();a[0]['library']['id']=456
        self.assertTrue(gate.compare(m,a))
        m,a=self.fixture();a.append({'key':'IJKLMNOP','library':{'type':'user','id':123},'data':{}})
        self.assertTrue(gate.compare(m,a))
    def test_cli_order_and_no_output_on_failure(self):
        m,a=self.fixture()
        other=copy.deepcopy(m['records'][0]);other.update(ref='b',key='IJKLMNOP');other['expected']['DOI']='10.example/b';other['expected']['title']='B test article'
        m['records']=[other,m['records'][0]]
        b=copy.deepcopy(a[0]);b['key']='IJKLMNOP';b['data']=copy.deepcopy(other['expected']);b['bib']='<div>1. Frerichs I. B test article. Example J. 2023.</div>';a.append(b)
        m.update(style='vancouver',locale='en-US',numbering='citation-order',citation_order=['b','a','b'],formatted_with={'style':'vancouver','locale':'en-US'})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snap=root/'manuscript.txt';snap.write_text('B first, then A, then B.')
            m['manuscript']={'path':'manuscript.txt','sha256':hashlib.sha256(snap.read_bytes()).hexdigest()}
            mp=root/'manifest.json';ap=root/'actual.json';mp.write_text(json.dumps(m));ap.write_text(json.dumps(a))
            cmd=[sys.executable,str(Path(gate.__file__)),str(mp),'--actual',str(ap),'--out',str(root/'ok')]
            p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            txt=(root/'ok/references.txt').read_text();self.assertTrue(txt.startswith('[1] Frerichs I. B test'));self.assertIn('[2] Frerichs I. A test',txt)
            a[0]['data']['pages']='771-783';ap.write_text(json.dumps(a));cmd[-1]=str(root/'bad')
            p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,2);self.assertFalse((root/'bad/references.txt').exists())
            a[0]['data']['pages']='770-783';ap.write_text(json.dumps(a));snap.write_text('changed manuscript');cmd[-1]=str(root/'stale')
            p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,2);self.assertFalse((root/'stale/references.txt').exists())

if __name__=='__main__':unittest.main()
