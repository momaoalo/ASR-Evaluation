"""Run the included offline tests and save a truthful local result summary."""
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import unittest

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        'at': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
        'tests': result.testsRun, 'passed': result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        'skipped': [{'test': str(t), 'reason': reason} for t,reason in result.skipped],
        'failures': len(result.failures), 'errors': len(result.errors),
        'scope': 'Offline unit/integration tests. Provider network transports are mocked; no paid API requests.'
    }
    target = root / 'verification/local_test_results.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
