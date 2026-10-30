"""Build and validate the codebook field table."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from preprocessing.metadata.codebook import CODEBOOK_DIR
from preprocessing.metadata.registry import iter_registry_fields
from preprocessing.metadata.schema import (
    VIEW_LEVELS,
    CodebookField,
    CodebookValidationError,
    read_fields,
    validate_codebook_package,
    write_fields,
)

__all__ = ["build_fields", "main"]

_VIEW_ORDER = {view: index for index, view in enumerate(VIEW_LEVELS)}


def _sort_key(field: CodebookField) -> tuple[int, str]:
    return (_VIEW_ORDER.get(field.view_level, len(VIEW_LEVELS)), field.variable_id)


def build_fields(codebook_dir: Path | str = CODEBOOK_DIR) -> list[CodebookField]:
    """Combine registered output fields with curated source rows."""
    source = Path(codebook_dir)
    existing = read_fields(source / "fields.csv")
    registered = list(iter_registry_fields())
    registered_ids = {field.variable_id for field in registered}
    curated = [field for field in existing if field.variable_id not in registered_ids]
    return sorted([*curated, *registered], key=_sort_key)


def _row_differences(
    actual: Sequence[CodebookField],
    expected: Sequence[CodebookField],
) -> list[str]:
    differences: list[str] = []
    actual_by_id = {field.variable_id: field for field in actual}
    expected_by_id = {field.variable_id: field for field in expected}

    for variable_id in sorted(expected_by_id.keys() - actual_by_id.keys()):
        differences.append(f"Missing from fields.csv: {variable_id}")
    for variable_id in sorted(actual_by_id.keys() - expected_by_id.keys()):
        differences.append(f"Unexpected in fields.csv: {variable_id}")
    for variable_id in sorted(actual_by_id.keys() & expected_by_id.keys()):
        if actual_by_id[variable_id].to_row() != expected_by_id[variable_id].to_row():
            differences.append(f"Row differs from registry: {variable_id}")
    return differences


def main(argv: Sequence[str] | None = None) -> int:
    """Run the codebook build or check."""
    parser = argparse.ArgumentParser(
        description="Build and validate the codebook field table."
    )
    parser.add_argument(
        "--codebook-dir",
        type=Path,
        default=CODEBOOK_DIR,
        help="Codebook package directory. Defaults to the repository codebook folder.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write fields.csv from the field registry.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check fields.csv and the package without writing. This is the default.",
    )
    args = parser.parse_args(argv)
    if args.write and args.check:
        parser.error("--write and --check cannot be used together")

    try:
        expected = build_fields(args.codebook_dir)
        if args.write:
            write_fields(args.codebook_dir / "fields.csv", expected)
            validate_codebook_package(args.codebook_dir)
            print(f"Wrote {len(expected)} fields to {args.codebook_dir / 'fields.csv'}")
            return 0

        actual = read_fields(args.codebook_dir / "fields.csv")
        differences = _row_differences(actual, expected)
        if differences:
            print("codebook/fields.csv is out of date.")
            for difference in differences:
                print(f"* {difference}")
            print(
                "Run "
                f"`uv run python -m preprocessing.scripts.build_codebook "
                f"--codebook-dir {args.codebook_dir} --write` to update it."
            )
            return 1

        validate_codebook_package(args.codebook_dir)
    except CodebookValidationError as error:
        print(error)
        return 1

    print(f"Codebook package is valid with {len(expected)} fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
