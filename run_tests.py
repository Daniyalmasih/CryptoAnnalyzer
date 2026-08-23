#!/usr/bin/env python
"""Run all tests for CryptoAnalyzer."""
import sys
import os
import unittest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def run_tests():
    """Run all test suites."""
    print("🚀 Running CryptoAnalyzer Tests")
    print("=" * 50)
    
    # Discover and run tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    print("=" * 50)
    print(f"✅ Tests completed: {result.testsRun} run, "
          f"{len(result.failures)} failures, "
          f"{len(result.errors)} errors, "
          f"{len(result.skipped)} skipped")
    
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())