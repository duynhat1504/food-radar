"""Static OpenAPI + synthetic policy checks. NOT a live Google or load test."""
from pathlib import Path
import math
import json
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/'docs/openapi.yaml'
SRS=ROOT/'docs/product-requirements.md'
ADR4=ROOT/'docs/adr/0004-google-places-provider.md'
ADR5=ROOT/'docs/adr/0005-recommendation-strategy.md'
ADR9=ROOT/'docs/adr/0009-candidate-retrieval.md'
doc=yaml.safe_load(SPEC.read_text(encoding='utf-8'))


def resolve_local(ref):
    assert ref.startswith('#/'),ref
    v=doc
    for token in ref[2:].split('/'):
        v=v[token.replace('~1','/').replace('~0','~')]
    return v


def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)


class FakeProvider:
    def __init__(self): self.calls=0
    def nearby(self,request):
        self.calls+=1
        return [{'id':'synthetic-A','name':'Synthetic A'},{'id':'synthetic-B','name':'Synthetic B'}]
    def text(self,request):
        self.calls+=1
        return [{'id':'synthetic-T','name':'Synthetic T'}]


def route_google(req,provider):
    """Pure synthetic *policy* stub, not a licensed production adapter."""
    assert req.get('sourceMode','GOOGLE_DISCOVERY')=='GOOGLE_DISCOVERY'
    r=req.get('radiusMeters',0); lat=req.get('latitude',999); lon=req.get('longitude',999)
    if not (100<=r<=10000 and -90<=lat<=90 and -180<=lon<=180):
        return 400, {'code':'INVALID_SEARCH_REQUEST'}
    query=(req.get('query') or '').strip()
    if len(query)>120:return 400,{'code':'INVALID_SEARCH_REQUEST'}
    if (query and 'placeType' in req) or req.get('openNow') is True or req.get('minRating') is not None or req.get('minUserRatingCount') is not None or req.get('rankingMode','PROVIDER_ORDER')!='PROVIDER_ORDER':
        return 422,{'code':'UNSUPPORTED_FILTER_FOR_SOURCE'}
    if query:
        candidates=provider.text(req)
        return 200,{'sourceMode':'GOOGLE_DISCOVERY','retrievalMode':'GOOGLE_TEXT','rankingMode':'PROVIDER_ORDER','radiusPolicy':'PROVIDER_BIAS_ONLY','isRadiusStrict':False,'isExhaustive':False,'candidateCount':len(candidates),'results':candidates,'foodRadarScore':None,'scoreVersion':None}
    candidates=provider.nearby(req)
    return 200,{'sourceMode':'GOOGLE_DISCOVERY','retrievalMode':'GOOGLE_NEARBY','rankingMode':'PROVIDER_ORDER','radiusPolicy':'PROVIDER_CIRCLE_RESTRICTION','isRadiusStrict':True,'isExhaustive':False,'candidateCount':len(candidates),'results':candidates,'foodRadarScore':None,'scoreVersion':None}


def bayesian(r,v,m=20,c=4.0):return v/(v+m)*r + m/(v+m)*c

def owned_score(rating,reviews,distance,rad,category=0.5,context=0.5):
    adj=.5 if rating is None or reviews is None else bayesian(rating,reviews)/5
    d=max(0,1-distance/rad)
    return round(.4*adj+.3*d+.2*category+.1*context,8)

class ContractChecks(unittest.TestCase):
    def test_01_parse_and_ref_resolution(self):
        self.assertEqual(doc['openapi'],'3.0.3')
        for obj in walk(doc):
            if '$ref' in obj: self.assertIsInstance(resolve_local(obj['$ref']),dict)
    def test_02_unique_operations_and_13_ops(self):
        ops=[op['operationId'] for methods in doc['paths'].values() for method,op in methods.items() if method in ('get','post','put','patch','delete')]
        self.assertEqual(len(ops),13);self.assertEqual(len(ops),len(set(ops)))
    def test_03_all_srs_api_modules(self):
        for p in ('/api/v1/auth/register','/api/v1/auth/login','/api/v1/auth/refresh','/api/v1/auth/logout','/api/v1/users/me','/api/v1/users/me/preferences','/api/v1/places/search','/api/v1/favorites'):
            self.assertIn(p,doc['paths'])
        self.assertNotIn('/api/v1/recommendations/feedback',doc['paths'])
    def test_04_source_enum_mode(self):
        q=doc['components']['schemas']['SearchRequest']['properties']
        self.assertEqual(q['sourceMode']['enum'],['GOOGLE_DISCOVERY','OWNED_DATA'])
        self.assertIn('PROVIDER_ORDER',q['rankingMode']['enum'])
    def test_05_google_response_requires_provenance(self):
        p=doc['components']['schemas']['SearchResponse']; required=p['required']
        for field in ('sourceMode','radiusPolicy','isRadiusStrict','isExhaustive','candidateCount','coverageNotice','results'):self.assertIn(field,required)
        example=doc['paths']['/api/v1/places/search']['post']['responses']['200']['content']['application/json']['example']
        self.assertEqual(example['radiusPolicy'],'PROVIDER_BIAS_ONLY'); self.assertFalse(example['isRadiusStrict']);self.assertIsNone(example['scoreVersion'])
        self.assertNotIn('foodRadarScore',example['results'][0]);self.assertNotIn('distanceMeters',example['results'][0])
    def test_06_errors(self):
        responses=doc['paths']['/api/v1/places/search']['post']['responses']
        for status in ('400','422','429','502','503','504'): self.assertIn(status,responses)
        self.assertIn('CLIENT_RATE_LIMITED',SRS.read_text(encoding='utf-8'))
        self.assertIn('PROVIDER_QUOTA_EXHAUSTED',SRS.read_text(encoding='utf-8'))
    def test_07_routing_nearby_one_call(self):
        stub=FakeProvider();code,r=route_google({'latitude':10.7,'longitude':106.7,'radiusMeters':5000},stub)
        self.assertEqual(code,200);self.assertEqual(stub.calls,1);self.assertEqual(r['retrievalMode'],'GOOGLE_NEARBY');self.assertTrue(r['isRadiusStrict'])
    def test_08_routing_text_is_bias_not_strict(self):
        stub=FakeProvider();code,r=route_google({'latitude':10.7,'longitude':106.7,'radiusMeters':5000,'query':' phở '},stub)
        self.assertEqual(code,200);self.assertEqual(stub.calls,1);self.assertEqual(r['retrievalMode'],'GOOGLE_TEXT');self.assertFalse(r['isRadiusStrict']);self.assertFalse(r['isExhaustive'])
    def test_09_google_invalid_filters_zero_calls(self):
        for field,value in [('minRating',4.3),('minUserRatingCount',50),('openNow',True),('rankingMode','RATING')]:
            stub=FakeProvider();code,r=route_google({'latitude':10.7,'longitude':106.7,'radiusMeters':5000,field:value},stub)
            self.assertEqual(code,422);self.assertEqual(stub.calls,0)
        stub=FakeProvider();code,_=route_google({'latitude':10.7,'longitude':106.7,'radiusMeters':5000,'query':'pho','placeType':'cafe'},stub)
        self.assertEqual(code,422);self.assertEqual(stub.calls,0)
    def test_10_validation_no_google_calls(self):
        for r in (0,99,10001):
            stub=FakeProvider();code,_=route_google({'latitude':10.7,'longitude':106.7,'radiusMeters':r},stub)
            self.assertEqual(code,400);self.assertEqual(stub.calls,0)
    def test_11_google_preserves_order_no_derived_score(self):
        stub=FakeProvider();code,result=route_google({'latitude':10.7,'longitude':106.7,'radiusMeters':300},stub)
        self.assertEqual([x['id'] for x in result['results']],['synthetic-A','synthetic-B']);self.assertIsNone(result['foodRadarScore']);self.assertIsNone(result['scoreVersion'])
    def test_12_owned_score_bounds_and_distance_monotonic(self):
        score1=owned_score(4.7,1200,100,5000);score2=owned_score(4.7,1200,4000,5000)
        self.assertGreater(score1,score2)
        for t in (score1,score2,owned_score(None,None,500,5000)):
            self.assertGreaterEqual(t,0);self.assertLessEqual(t,1)
    def test_13_adjusted_rating_reduces_sparse_bias(self):
        self.assertLess(bayesian(5.0,2),bayesian(4.7,1200))
    def test_14_doc_policy_consistency(self):
        for doc_path in (ADR4,ADR5,ADR9,SRS):
            s=doc_path.read_text(encoding='utf-8')
            self.assertIn('GOOGLE_DISCOVERY',s)
        self.assertIn('PROVIDER_BIAS_ONLY',ADR9.read_text(encoding='utf-8'))
        self.assertIn('OWNED_DATA',ADR5.read_text(encoding='utf-8'))
    def test_15_security_contract(self):
        schemes=doc['components']['securitySchemes']
        self.assertIn('refreshCookie',schemes)
        for endpoint in ['/api/v1/auth/refresh','/api/v1/auth/logout']:
            params=doc['paths'][endpoint]['post']['parameters']
            self.assertTrue(any(p['name']=='X-CSRF-Token' and p['required'] for p in params))
    def test_16_no_google_raw_cache_in_documents(self):
        s=ADR4.read_text(encoding='utf-8').lower(); self.assertIn('không cache',s);self.assertIn('place id',s)

if __name__=='__main__':unittest.main(verbosity=2)
