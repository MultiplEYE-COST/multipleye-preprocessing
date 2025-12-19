"""Main script for the psychmetric test processing."""

import argparse
from pathlib import Path

from ..config import PSYCHOMETRIC_TESTS_DIR
from ..psychometric_tests.preprocess_psychometric_tests import preprocess_all_sessions


def process_all_psychometric_test_sessions():
    """Entry point for processing psychometric test sessions."""
    parser = argparse.ArgumentParser(
        description="Process all psychometric test sessions."
    )
    parser.add_argument(
        '--test-session-folder',
        type=str,
        help='Path to the folder containing the psychometric test sessions.',
        default=PSYCHOMETRIC_TESTS_DIR
    )

    args = parser.parse_args()

    print(f"Processing psychometric test sessions from {args.test_session_folder}")

    preprocess_all_sessions(Path(args.test_session_folder))
