"""Provider selection shared by installation and application startup."""
import argparse
import json
import os
from pathlib import Path
import tempfile

MODES = {'codex': ['codex'], 'claude': ['claude'], 'both': ['codex', 'claude']}


def selected(settings):
    return list(MODES.get(settings.get('providers'), MODES['both']))


def create_adapters(settings):
    adapters = {}
    for key in selected(settings):
        if key == 'codex':
            from core import Codex
            adapters[key] = Codex()
        else:
            from bridge import ExtensionQuota
            adapters[key] = ExtensionQuota()
    return adapters


def configure(path, mode):
    if mode not in MODES:
        raise ValueError('Unsupported provider selection')
    path = Path(path)
    try:
        settings = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        settings = {}
    if not isinstance(settings, dict):
        raise ValueError('Existing settings must be a JSON object')
    settings['providers'] = mode
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(settings, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--providers', choices=MODES, required=True)
    args = parser.parse_args()
    configure(Path(__file__).resolve().parent / '.runtime/settings.json', args.providers)
    print('Selected providers: ' + args.providers)
