import json
import unittest
import urllib.request
import urllib.error
from bridge import ExtensionQuota, validate_rows, PORT

class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = ExtensionQuota(port=0)
        if cls.bridge.start_error:
            raise RuntimeError('Stop Quota Glance before running bridge integration tests')

    @classmethod
    def tearDownClass(cls):
        cls.bridge.close()

    def send(self, payload, token):
        req = urllib.request.Request(f'http://127.0.0.1:{self.bridge.port}/quota',json.dumps(payload).encode(),
                                     {'Content-Type':'application/json','Authorization':'Bearer '+token})
        return urllib.request.urlopen(req,timeout=3)

    def test_unauthorized_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.send({'rows':[]},'wrong')
        self.assertEqual(e.exception.code,401)

    def test_unknown_channel_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.send({'account':'gemini-personal','rows':[]},self.bridge.token)
        self.assertEqual(e.exception.code,400)

    def test_rows_and_stale(self):
        rows = [{'label':'Current session','remaining':52}]
        with self.send({'rows':rows},self.bridge.token) as r:
            self.assertEqual(r.status,200)
        self.assertEqual(self.bridge.fetch()[0]['remaining'],52)
        self.bridge.received -= 160
        with self.assertRaisesRegex(RuntimeError,'수신 중단'):
            self.bridge.fetch()

    def test_invalid_percent_rejected(self):
        for value in [None,True,-1,101,'25',float('nan')]:
            with self.assertRaises(ValueError):
                validate_rows([{'label':'session','remaining':value}])

    def test_reset_credits_round_trip(self):
        rows = [{'label':'session','remaining':98},
                {'kind':'resetCredit','label':'전체 초기화','resetText':'만료일: 10월 23일'}]
        with self.send({'rows':rows},self.bridge.token):
            pass
        self.assertEqual(self.bridge.fetch()[1],rows[1])

    def test_invalid_reset_credit_rejected(self):
        for detail in [None, '', 3, 'x'*201]:
            with self.assertRaises(ValueError):
                validate_rows([{'kind':'resetCredit','label':'전체 초기화','resetText':detail}])

    def test_pair_returns_auto_open_without_fabricating_usage(self):
        req = urllib.request.Request(f'http://127.0.0.1:{self.bridge.port}/pair',
            json.dumps({'version':'1.3.0'}).encode(),
            {'Content-Type':'application/json','Authorization':'Bearer '+self.bridge.token})
        before = self.bridge.received
        with urllib.request.urlopen(req,timeout=3) as response:
            self.assertTrue(json.load(response)['autoOpen'])
        self.assertEqual(self.bridge.extension_version,'1.3.0')
        self.assertEqual(self.bridge.received,before)

    def test_background_problem_preserves_observation_time(self):
        before = self.bridge.received
        req = urllib.request.Request(f'http://127.0.0.1:{self.bridge.port}/pair',
            json.dumps({'version':'1.4.0','problem':'sleeping'}).encode(),
            {'Content-Type':'application/json','Authorization':'Bearer '+self.bridge.token})
        with urllib.request.urlopen(req,timeout=3):
            pass
        self.assertEqual(self.bridge.received,before)
        self.assertIn('정지',self.bridge.error)

    def test_empty_read_preserves_previous_as_error(self):
        with self.send({'rows':[{'label':'week','remaining':40}]},self.bridge.token):
            pass
        with self.send({'rows':[]},self.bridge.token):
            pass
        self.assertEqual(self.bridge.rows[0]['remaining'],40)
        with self.assertRaisesRegex(RuntimeError,'화면 대기'):
            self.bridge.fetch()

if __name__=='__main__':
    unittest.main()
