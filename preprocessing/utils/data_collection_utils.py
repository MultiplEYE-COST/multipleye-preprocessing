from pathlib import Path


def _report_to_file(message: str, report_file: Path):
    """
    Write a message to a file.
    :param message: Message to write
    :param report_file: Path to report file
    :return:
    """
    assert isinstance(report_file, Path)
    with open(report_file, "a", encoding="utf-8") as report_file:
        report_file.write(f"{message}\n")
