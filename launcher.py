"""PyInstaller entry point. Worker events use files, including in windowed mode."""
from leafpress.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
