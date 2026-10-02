import json
import time
import unittest
import urllib.request
from bridge import ExtensionQuota, validate_credits


class ResetActionsTests(unittest.TestCase):
    def setUp(self):
        self.bridge = ExtensionQuota(port=0, auto_open=False)
        self.addCleanup(self.bridge.close)
        self.item = {'label':'전체 재설정','detail':'10월 5일 만료',
                     'identity':'["전체 재설정","10월 5일 만료"]','available':True}

    def post(self, path, body):
        request = urllib.request.Request(f'http://127.0.0.1:{self.bridge.port}{path}',
            json.dumps(body).encode(),{'Content-Type':'application/json','Authorization':'Bearer '+self.bridge.token})
        with urllib.request.urlopen(request,timeout=3) as response:
            return json.load(response)

    def test_roundtrip_one_shot_and_result(self):
        self.post('/credits',{'account':'codex','credits':[self.item]})
        request_id = self.bridge.reveal_credit('codex',self.item['identity'])
        # Ordinary heartbeat must not consume a selection command.
        self.assertIsNone(self.post('/pair',{'version':'1.6.0'})['resetCommand'])
        with self.assertRaisesRegex(RuntimeError,'처리 중'):
            self.bridge.reveal_credit('codex',self.item['identity'])
        response = self.post('/pair',{'version':'1.6.0','resetPoll':True})
        self.assertFalse(response['autoOpen'])
        self.assertEqual(response['resetCommand']['id'],request_id)
        self.assertEqual(response['resetCommand']['action'],'reveal')
        self.assertIsNone(self.post('/pair',{'resetPoll':True})['resetCommand'])
        self.post('/reset-result',{'id':'wrong','ok':True,'message':'ignored'})
        self.assertFalse(self.bridge.credit_result(request_id)['done'])
        self.post('/reset-result',{'id':request_id,'ok':True,'message':'공식 화면에서 사용'})
        self.assertTrue(self.bridge.credit_result(request_id)['done'])

    def test_stale_and_changed_identity_rejected(self):
        self.post('/credits',{'account':'codex','credits':[self.item]})
        with self.assertRaisesRegex(RuntimeError,'변경'):
            self.bridge.reveal_credit('codex','different')
        self.bridge.credits['codex']['received'] -= 100
        with self.assertRaisesRegex(RuntimeError,'오래'):
            self.bridge.reveal_credit('codex',self.item['identity'])

    def test_expired_command_not_dispatched(self):
        self.post('/credits',{'account':'codex','credits':[self.item]})
        self.bridge.reveal_credit('codex',self.item['identity'])
        self.bridge.reset_command['created'] = time.time()-61
        self.assertIsNone(self.post('/pair',{'resetPoll':True})['resetCommand'])

    def test_empty_clears_credits_and_validation(self):
        self.post('/credits',{'account':'codex','credits':[self.item]})
        self.post('/credits',{'account':'codex','credits':[]})
        self.assertEqual(self.bridge.credit_snapshot('codex')['items'],[])
        for item in [dict(self.item,available='yes'),dict(self.item,identity=''),dict(self.item,detail='x'*201)]:
            with self.assertRaises(ValueError):
                validate_credits([item])

    def test_use_binds_tab_and_blocks_duplicate_or_disabled(self):
        self.post('/credits',{'account':'codex','credits':[self.item],'tabId':42})
        request_id = self.bridge.reveal_credit('codex',self.item['identity'],consume=True)
        command = self.post('/pair',{'resetPoll':True})['resetCommand']
        self.assertEqual(command['action'],'use')
        self.assertEqual(command['tabId'],42)
        self.post('/reset-result',{'id':request_id,'ok':False,'message':'결과 미확인'})
        with self.assertRaisesRegex(RuntimeError,'이미 사용'):
            self.bridge.reveal_credit('codex',self.item['identity'],consume=True)
        self.post('/credits',{'account':'codex','credits':[dict(self.item,available=False)],'tabId':42})
        with self.assertRaisesRegex(RuntimeError,'사용할 수 없는'):
            self.bridge.reveal_credit('codex',self.item['identity'],consume=True)


if __name__=='__main__':
    unittest.main()
