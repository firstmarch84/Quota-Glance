import unittest
from unittest.mock import patch, Mock
import startup


class StartupTests(unittest.TestCase):
    @patch('startup.command', return_value=b'{"enabled":false,"valid":true,"disabled":true}')
    def test_windows_disabled_is_unchecked(self, command):
        self.assertFalse(startup.status()['enabled'])

    @patch('startup.command', side_effect=OSError('unavailable'))
    def test_cannot_verify_is_not_checked(self, command):
        self.assertFalse(startup.status()['enabled'])

    @patch('startup.status', return_value={'enabled':False,'disabled':True})
    @patch('startup.command')
    def test_disabled_registration_reports_action(self, command, status):
        with self.assertRaisesRegex(RuntimeError, 'Windows'):
            startup.enable()

    @patch('startup.subprocess.run', return_value=Mock(returncode=0, stdout=b'{}'))
    def test_uses_current_python_explicitly(self, run):
        startup.command('-Status')
        args = run.call_args.args[0]
        self.assertEqual(args[args.index('-PythonPath')+1], startup.sys.executable)


if __name__ == '__main__':
    unittest.main()
