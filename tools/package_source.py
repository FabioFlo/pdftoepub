"""Bundle the working release source without environments or private inputs."""
from pathlib import Path
import argparse
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    files = []
    for directory in ("leafpress", "tests", "tools", "docs", "examples", ".github"):
        files.extend(path for path in (project / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    for filename in (".gitignore", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "START_HERE_IT.md",
                     "PROJECT_CONTEXT.md", "CHANGELOG.md", "pyproject.toml", "launcher.py", "start.sh",
                     "setup-windows.bat", "start-windows.bat", "build-windows.bat"):
        path = project / filename
        if path.is_file():
            files.append(path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            archive.write(path, "LeafPress/" + path.relative_to(project).as_posix())
    print(args.output)


if __name__ == "__main__":
    main()
