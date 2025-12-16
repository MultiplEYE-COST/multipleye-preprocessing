"""Utilities to parse and store answers to comprehension questions.

Provide focused helpers to:
- read the per-trial question order (11/12/21/22/31/32) from the session CSV,
- construct canonical question identifiers (e.g., 10111 or 20221),
- collect a per-session table with one row per asked question (6 per trial),
- write/read that table from CSV.
"""
