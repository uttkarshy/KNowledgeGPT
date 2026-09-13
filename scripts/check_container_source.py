"""Compare executed Python modules against host files; print hashes, never secrets.

Host: python scripts/check_container_source.py
Container: python /opt/knowledgegpt-scripts/check_container_source.py --inside
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

MODULES = [
    'app.core.config', 'app.services.llm.gemini_provider',
    'app.services.embedding.pipeline', 'app.workers.tasks.document_processing',
    'app.services.rag.engine', 'app.services.rag.retrieval',
]


def fingerprint():
    sys.path.insert(0, '/app')
    output = {}
    for name in MODULES:
        path = Path(importlib.import_module(name).__file__)
        output[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project')
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.inside:
        print(json.dumps(fingerprint(), sort_keys=True))
        return
    root = Path(__file__).resolve().parents[1]
    expected = {name: hashlib.sha256((root / 'backend' / (name.replace('.', '/') + '.py')).read_bytes()).hexdigest() for name in MODULES}
    command = ['docker', 'compose'] + (['-p', args.project] if args.project else [])
    for service in ('backend', 'celery-worker'):
        result = subprocess.run(command + ['exec', '-T', service, 'python', '-c',
            'import runpy; runpy.run_path("/opt/knowledgegpt-scripts/check_container_source.py", run_name="__main__")', '--inside'],
            cwd=root, text=True, capture_output=True, check=True)
        actual = json.loads(result.stdout)
        if actual != expected:
            raise SystemExit(f'FAIL: {service} source differs from checkout; rebuild with --no-cache')
        print(f'PASS: {service} executed module hashes match checkout')


if __name__ == '__main__':
    main()
