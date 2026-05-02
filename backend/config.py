from pathlib import Path

from dotenv import load_dotenv


def load_environment(env_path: str | Path | None = None) -> None:
    path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(path, override=False)
