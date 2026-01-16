"""
Test runner for the entire test suite.

Usage:
    python tests/run_tests.py                    # Run all tests
    python tests/run_tests.py test_icap_adapter  # Run specific test module
    python tests/run_tests.py --verbose          # Verbose output
"""

import sys
import unittest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """Run all tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run test suite")
    parser.add_argument(
        'test_module',
        nargs='?',
        help='Specific test module to run (e.g., test_icap_adapter)',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output',
    )
    parser.add_argument(
        '--failfast',
        action='store_true',
        help='Stop on first failure',
    )
    
    args = parser.parse_args()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    if args.test_module:
        # Load specific test module
        try:
            module = loader.loadTestsFromName(f'tests.{args.test_module}')
            suite.addTest(module)
        except AttributeError:
            print(f"Error: Test module '{args.test_module}' not found")
            print("\nAvailable test modules:")
            test_files = list(Path(__file__).parent.glob('test_*.py'))
            for tf in test_files:
                print(f"  - {tf.stem}")
            return 1
    else:
        # Load all tests
        suite = loader.discover(
            str(Path(__file__).parent),
            pattern='test_*.py',
        )
    
    # Run tests
    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        failfast=args.failfast,
    )
    
    result = runner.run(suite)
    
    # Return exit code based on results
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
