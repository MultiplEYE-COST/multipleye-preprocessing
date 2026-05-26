import sys
import re
import argparse
from pathlib import Path

# Paths to files and the regex to find the version string in each
FILES_TO_UPDATE = {
    "pyproject.toml": (r'(version\s*=\s*")([^"]+)(")', r"\1{version}\3"),
    "CITATION.cff": (r"(^version:\s*)(.*)", r"\1{version}"),
    "docs/conf.py": (r'(release\s*=\s*")([^"]+)(")', r"\1{version}\3"),
}


def get_current_version():
    """Extracts the version string from pyproject.toml."""
    path = Path("pyproject.toml")
    if not path.exists():
        return None
    content = path.read_text()
    match = re.search(FILES_TO_UPDATE["pyproject.toml"][0], content)
    return match.group(2) if match else None


def update_files(new_version: str):
    """Updates the version string in all configured files."""
    for file_name, (pattern, replacement_template) in FILES_TO_UPDATE.items():
        path = Path(file_name)
        if not path.exists():
            print(f"Warning: {file_name} not found. Skipping.")
            continue

        content = path.read_text()

        def replace_func(match):
            # match.group(1) is the prefix (e.g., 'version = "')
            # match.group(3) is the suffix (e.g., '"') if it exists
            prefix = match.group(1)
            try:
                suffix = match.group(3)
            except IndexError:
                suffix = ""
            return f"{prefix}{new_version}{suffix}"

        new_content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)

        if content != new_content:
            path.write_text(new_content)
            print(f"Updated {file_name} to {new_version}")


def validate_format(version: str):
    """Validates that the version follows the YYYY.MM.DD format."""
    if not re.match(r"^\d{4}\.\d{2}\.\d{2}$", version):
        print(f"Error: Version '{version}' does not match CalVer format YYYY.MM.DD")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Synchronize version strings across project files."
    )
    parser.add_argument(
        "--set-version", help="Update all files to this specific version"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate current version format in pyproject.toml",
    )

    args = parser.parse_args()
    current = get_current_version()

    if args.set_version:
        validate_format(args.set_version)
        update_files(args.set_version)
    elif args.validate:
        if not current:
            print("Error: Could not find version in pyproject.toml")
            sys.exit(1)
        validate_format(current)
        print(f"Version {current} is valid.")
    else:
        # Default behavior: Sync all files based on whatever is in pyproject.toml
        if current:
            update_files(current)
        else:
            print("Error: Could not find version in pyproject.toml")
            sys.exit(1)
