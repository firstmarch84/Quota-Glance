import unittest
from core import normalize_codex, BrowserQuota, is_usage_page, is_challenge_title
from unittest.mock import Mock

class QuotaTests(unittest.TestCase):
    def test_login_return_url_is_not_usage(self):
        self.assertFalse(is_usage_page('https://claude.ai/login?returnTo=/settings/usage','claude'))
        self.assertTrue(is_usage_page('https://claude.ai/settings/usage?x=1','claude'))
        self.assertFalse(is_usage_page('https://example.com/settings/usage','claude'))

    def test_challenge_never_reload_or_execute(self):
        b = BrowserQuota('test-claude','claude')
        b.enabled = True
        b.start = Mock()
        b.target = Mock(return_value={'title':'잠시만 기다리십시오…','url':'https://claude.ai/settings/usage'})
        b.call = Mock()
        with self.assertRaisesRegex(RuntimeError,'사람 확인'):
            b.fetch()
        b.call.assert_not_called()

    def test_unknown_page_never_reload(self):
        b = BrowserQuota('test-claude','claude')
        b.enabled = True
        b.start = Mock()
        b.target = Mock(return_value={'title':'Claude','url':'https://claude.ai/settings/usage'})
        b.call = Mock(return_value={'result':{'value':[]}})
        with self.assertRaises(RuntimeError):
            b.fetch()
        self.assertEqual([c.args[1] for c in b.call.call_args_list],['Runtime.evaluate'])

    def test_null_is_not_zero(self):
        self.assertEqual(normalize_codex({'rateLimits':{'primary':{'usedPercent':None}}}),[])

    def test_windows(self):
        result = normalize_codex({'rateLimits':{'primary':{'usedPercent':24,'windowDurationMins':300,'resetsAt':10},'secondary':{'usedPercent':100,'windowDurationMins':10080}}})
        self.assertEqual([r['remaining'] for r in result],[76,0])
        self.assertEqual([r['label'] for r in result],['5시간','주간'])

    def test_buckets_preferred_without_duplicate_legacy(self):
        r = normalize_codex({'rateLimits':{'primary':{'usedPercent':80}},'rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':10}}}})
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['remaining'],90)

    def test_invalid_data(self):
        for value in [True,-10,101,'25',float('nan')]:
            self.assertEqual(normalize_codex({'rateLimits':{'primary':{'usedPercent':value}}}),[])

if __name__=='__main__':
    unittest.main()
