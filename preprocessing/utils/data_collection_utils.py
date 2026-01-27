from pathlib import Path


def _report_to_file(message: str, report_file: Path) -> None:
    """Writes a message to the specified report file.

    If the file does not exist, it creates the file and appends the message.
    Ensures the use of UTF-8 encoding.

    Parameters
    ----------
    message : str
        The message to be written to the file.
    report_file : Path
        The path to the file where the message will be appended.
    """
    assert isinstance(report_file, Path)
    with open(report_file, "a", encoding="utf-8") as report_file:
        report_file.write(f"{message}\n")
