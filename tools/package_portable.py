"""Create native download archives, preserving Unix permissions and app symlinks."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

NAME = 'PdfToEpubConverter'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('platform', choices=['Windows-x64', 'macOS-arm64', 'macOS-x64', 'Ubuntu-x64'])
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    output = project / 'downloads'
    output.mkdir(exist_ok=True)
    mac = args.platform.startswith('macOS')
    root = project / 'dist' / (NAME + '.app' if mac else NAME)
    if not root.is_dir():
        raise FileNotFoundError(f'Build output missing: {root}')
    resources = root / 'Contents' / 'Resources' if mac else root
    resources.mkdir(parents=True, exist_ok=True)
    for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(project / name, resources / name)
    shutil.copytree(project / 'examples', resources / 'examples', dirs_exist_ok=True)
    instructions = {
        'Windows-x64': 'Extract the whole ZIP. Open PdfToEpubConverter.exe. Keep all accompanying files together.',
        'Ubuntu-x64': 'Extract the archive. Open PdfToEpubConverter inside its folder. Keep all accompanying files together. For terminal launch, use ./PdfToEpubConverter from that folder.',
        'macOS-arm64': 'Extract the ZIP. Move PdfToEpubConverter.app to Applications and open it. This build is for Apple Silicon Macs.',
        'macOS-x64': 'Extract the ZIP. Move PdfToEpubConverter.app to Applications and open it. This build is for Intel Macs.',
    }
    (resources / 'START_HERE.txt').write_text(
        'PdfToEpub converter\n\n' + instructions[args.platform] + '\n\n'
        'No Python installation is required. Open a PDF, use the Balanced profile, preview a page, then Create EPUB.\n'
        'Documentation: https://github.com/FabioFlo/pdftoepub#readme\n', encoding='utf-8')
    subprocess.run([sys.executable, str(project / 'tools/package_source.py'),
                    str(resources / (NAME + '-source.zip'))], check=True)
    stem = NAME + '-' + args.platform
    if mac:
        # Modifying bundle resources invalidates the previous ad-hoc signature.
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(root)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(root)], check=True)
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(root),
                        str(output / (stem + '.zip'))], check=True)
        archive = output / (stem + '.zip')
    elif args.platform == 'Ubuntu-x64':
        archive = output / (stem + '.tar.gz')
        with tarfile.open(archive, 'w:gz', dereference=False) as bundle:
            bundle.add(root, arcname=NAME)
    else:
        archive = Path(shutil.make_archive(str(output / stem), 'zip', root.parent, root.name))
    print(archive)


if __name__ == '__main__':
    main()
