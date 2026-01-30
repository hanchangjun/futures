from pathlib import Path


def send_file(file_path: Path, message: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(message + "\n", encoding="utf-8")
