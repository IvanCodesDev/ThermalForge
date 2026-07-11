import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    schema = create_app().openapi()
    Path("openapi.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
