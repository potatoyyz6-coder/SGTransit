from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import http.client
import json
import socket
import threading
import urllib.request

import pytest

from experiments.local_app import ASSETS, NETWORK_IMAGE, WEB, make_server
from experiments.local_planner import LocalPlanner, UserError, case_data
from sg_transit.lta import BusArrival
from sg_transit.snapshot_reference import SGT


class Clock:
    def __init__(self):
        self.time = datetime(2026, 10, 11, 10, 0, tzinfo=SGT)
        self.tick = 100.0

    def now(self):
        return self.time

    def mono(self):
        return self.tick

    def advance(self, seconds):
        self.time += timedelta(seconds=seconds)
        self.tick += seconds


class Provider:
    endpoint = 'https://example.invalid/fake-arrivals'

    def __init__(self, clock, fail=False, slow=False):
        self.clock, self.fail, self.slow, self.calls = clock, fail, slow, []

    def fetch(self, stop):
        self.calls.append(stop)
        self.clock.advance(31 if self.slow else .1)
        if self.fail:
            raise RuntimeError('private-key-do-not-leak')
        return []


@pytest.fixture
def setup(tmp_path):
    clock = Clock()
    provider = Provider(clock)
    planner = LocalPlanner(now=clock.now, clock=clock.mono, provider_factory=lambda: provider,
        raw_dir=tmp_path/'raw', saved_snapshot=tmp_path/'saved.jsonl')
    return planner, clock, provider


def test_two_cases_directions_and_explicit_coverage():
    school, home = case_data('school', 3), case_data('home', 3)
    assert len(school[0].stops) == 25 and len(home[0].stops) == 47
    assert len(school[5]) == 7212 and school[6]['complete']
    assert home[5] and not home[6]['complete'] and home[6]['method'] == 'bounded_corridor'
    assert any(r.services == ('151-D2', '61-D2') for r in home[5])
    for data in (school, home):
        for route in data[5]:
            assert route.transfers <= 5 and len(route.services) == len(set(route.services))
    with pytest.raises(UserError):
        case_data('school', 10)


def test_offline_plan_details_and_no_network(setup, monkeypatch):
    planner, clock, provider = setup
    assert [item['label'] for item in planner.config()['cases']] == [
        'Blk 18 → CDE', 'Information Technology → Signature Pk']
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected network')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    r = planner.plan({'case':'school', 'mode':'model'})
    assert r['candidate_count'] == 7212 and len(r['families']) == 8
    assert not provider.calls and not planner.raw_dir.exists()
    assert r['mode'] == 'model' and r['info']['requests'] == 0
    row = planner.detail({'plan_id': r['plan_id'], 'route_id': r['families'][0]['row']['id']})
    assert row['points'] and row['modeled_boardings'] == len(row['legs'])
    assert row['estimated_total_minutes'] == pytest.approx(42.6)
    assert all('106A-D1' not in f['row']['services'] for f in r['families'])
    with pytest.raises(UserError):
        planner.plan({'case':'school', 'buffer':False})
    with pytest.raises(UserError):
        planner.detail({'plan_id':r['plan_id'], 'route_id':'no-such-route'})
    clock.advance(3*3600+1)
    with pytest.raises(UserError, match='过期'):
        planner.detail({'plan_id':r['plan_id'], 'route_id':row['id']})


def test_live_consent_bounded_calls_rate_limit_and_raw_provenance(setup):
    planner, clock, provider = setup
    with pytest.raises(UserError, match='确认'):
        planner.plan({'case':'school','mode':'live'})
    assert not provider.calls
    r = planner.plan({'case':'school','mode':'live','consent':True})
    assert len(provider.calls) == len(set(provider.calls)) == r['info']['requests'] == 25
    assert r['eligible_count'] > 0
    records = [json.loads(x) for x in next(planner.raw_dir.glob('*.jsonl')).read_text().splitlines()]
    assert records[0]['topology_provenance']['raw_sha256']
    assert records[-1]['status'] == 'completed_single_round'
    assert all('route_id' not in x and 'plan_id' not in x for x in records)
    assert len(r['info']['raw_sha256']) == 64
    with pytest.raises(UserError) as err:
        planner.plan({'case':'school','mode':'live','consent':True})
    assert err.value.status == 429 and len(provider.calls) == 25


def test_provider_failure_is_sanitized_and_does_not_retry(setup):
    planner, _, provider = setup
    provider.fail = True
    r = planner.plan({'case':'school','mode':'live','consent':True})
    assert r['info']['warning'] and len(provider.calls) == 1
    assert r['eligible_count'] > 0
    assert 'private-key-do-not-leak' not in json.dumps(r)
    assert 'private-key-do-not-leak' not in next(planner.raw_dir.glob('*.jsonl')).read_text()


def test_deadline_stops_new_requests_and_missing_key_never_calls(setup):
    planner, clock, provider = setup
    provider.slow = True
    records, _, info = planner.collect(case_data('school',3), True)
    assert info['requests'] == len(provider.calls) == 3 and info['warning']
    clock.advance(100)
    def fail():
        raise ValueError('secret')
    planner.provider_factory=fail
    with pytest.raises(UserError, match='LTA_DATAMALL_API_KEY'):
        planner.collect(case_data('school',3), True)


def test_saved_mode_no_calls_and_cannot_refresh_into_today(setup):
    planner, clock, provider = setup
    row = dict(type='observation',bus_stop_code='42161',status='ok',arrivals=[],
        requested_at='2026-10-08T11:20:00+08:00',received_at='2026-10-08T11:20:01+08:00')
    planner.saved_snapshot.write_text(json.dumps(row)+'\n')
    r=planner.plan({'case':'school','mode':'saved'})
    assert r['decision_at'].startswith('2026-10-08') and not provider.calls
    selected=r['families'][0]['row']
    request=dict(plan_id=r['plan_id'], route_id=selected['id'], point=1, onboard=True)
    t=planner.onward(request)
    assert t['info']['source']=='saved_projection' and t['at'].startswith('2026-10-08')
    with pytest.raises(UserError, match='历史案例'):
        planner.onward({**request,'live':True,'consent':True})
    assert not provider.calls
    with pytest.raises(UserError):
        planner.plan({'case':'home','mode':'saved'})


def test_onward_continuation_history_and_repeated_wait_clock(setup):
    planner, clock, provider = setup
    r=planner.plan({'case':'school','mode':'model'})
    row=next(f['row'] for f in r['families'] if f['row']['services']==['173-D1','183-D1'])
    point=next(p['index'] for p in row['points'] if p['stop']=='28019')
    clock.advance(20*60)
    request=dict(plan_id=r['plan_id'],route_id=row['id'],point=point,onboard=True)
    t=planner.onward(request)
    assert t['eligible_count'] and not provider.calls
    continuation=[x for x in t['routes'] if x['services'][0]=='173-D1']
    assert continuation
    for x in continuation:
        l=x['legs'][0]
        assert l['wait_minutes']==l['transfer_minutes']==l['mean_boarding_delay_minutes']==0
        assert l['timing_source']=='same_vehicle_continuation'
        assert x['transfers']==len(x['legs'])-1
    waiting=planner.onward({**request,'onboard':False})
    assert all('173-D1' not in x['services'] for x in waiting['routes'])
    adopt=next(x for x in waiting['routes'] if x['can_adopt'])
    adopted=planner.detail({'plan_id':r['plan_id'], 'route_id':adopt['id']})
    assert any(p['stop']=='28019' for p in adopted['points'])
    clock.advance(46*60)
    late=planner.onward({**request,'onboard':False})
    assert late['eligible_count']==0
    assert late['exclusions']['estimated_transfer_gap_exceeded']>0
    with pytest.raises(UserError):
        planner.onward({**request,'point':999})


def test_live_onward_uses_fresh_capture_and_retains_root_history(setup):
    planner, clock, provider=setup
    r=planner.plan({'case':'home','mode':'model'})
    row=next(f['row'] for f in r['families'] if f['row']['services']==['151-D2','61-D2'])
    point=next(p['index'] for p in row['points'] if p['stop']=='12061')
    clock.advance(12*60)
    t=planner.onward(dict(plan_id=r['plan_id'],route_id=row['id'],point=point,onboard=True,live=True,consent=True))
    assert t['info']['requests']==47 and len(provider.calls)==47
    assert t['candidate_count']>0
    assert any(x['services'][0] in ('52-D2','61-D2','184-D1') for x in t['routes'])


def test_web_assets_and_http_security(setup):
    planner, _, provider=setup
    for filename, _ in ASSETS.values():
        assert (WEB/filename).is_file()
    assert NETWORK_IMAGE.is_file()
    server=make_server(0,planner)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    def request(path,method='GET',body=None,headers=None):
        client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=20)
        try:
            client.request(method,path,body,headers or {})
            response=client.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:
            client.close()
    try:
        code,headers,html=request('/')
        assert code==200 and 'frame-ancestors' in headers['Content-Security-Policy']
        assert '本机运行'.encode() in html
        code,_,raw=request('/api/config')
        config=json.loads(raw)
        assert code==200 and 'csrf' in config and 'key_present' in config
        assert request('/api/config',headers={'Host':'evil.example'})[0]==403
        assert request('/../.env')[0]==404
        assert request('/network.png')[0]==200
        assert request('/api/plan','POST','{}',{'Content-Type':'application/json','Origin':origin})[0]==403
        headers={'Content-Type':'application/json','Origin':'https://evil.example','X-CSRF-Token':config['csrf']}
        assert request('/api/plan','POST','{}',headers)[0]==403
        headers['Origin']=origin
        assert request('/api/plan','POST','[]',headers)[0]==400
        code,_,raw=request('/api/plan','POST',json.dumps({'case':'home','mode':'model'}),headers)
        assert code==200 and json.loads(raw)['families']
        plan_id=json.loads(raw)['plan_id']
        code,_,raw=request('/api/route-combinations','POST',json.dumps({'plan_id':plan_id}),headers)
        assert code==200 and json.loads(raw)['compatible_count']>0
        assert request('/api/route-combinations','POST','{}',{'Content-Type':'application/json','Origin':origin})[0]==403
        assert request('/api/route-combinations','POST',json.dumps({'plan_id':'expired'}),headers)[0]==410
        assert request('/api/route-combinations','POST',json.dumps({'plan_id':plan_id,'selection':[999999]}),headers)[0]==400
        assert request('/api/route-combinations','POST',json.dumps({'plan_id':plan_id}),{**headers,'Host':'evil.example'})[0]==403
        code,_,raw=request('/api/stops','POST',json.dumps({'network':'school','text':'42161'}),headers)
        assert code==200 and json.loads(raw)['stops'][0]['id']=='42161'
        code,_,raw=request('/api/nearby','POST',json.dumps({'network':'school','center':'42161'}),headers)
        assert code==200 and json.loads(raw)['unsupported_count']>0
        body=dict(query_type='stations',network='school',origins=[dict(stop='28109')],
                  destinations=[dict(stop='16159')],departure_time='2026-10-26T10:00')
        code,_,raw=request('/api/plan','POST',json.dumps(body),headers)
        assert code==200 and json.loads(raw)['query_type']=='stations'
        body['origins']=[dict(stop='42169')]
        code,_,raw=request('/api/plan','POST',json.dumps(body),headers)
        assert code==400 and json.loads(raw)['code']=='outside_network'
        assert request('/api/nearby','POST','{}',{'Content-Type':'application/json','Origin':origin})[0]==403
        assert not provider.calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
