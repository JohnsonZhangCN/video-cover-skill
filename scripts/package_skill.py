"""Build a portable skill ZIP with licenses and standalone install instructions."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / f'video-cover-skill-v{VERSION}.zip'
    skill = ROOT / 'skills' / 'video-cover'
    files = [(path, 'video-cover/' + path.relative_to(skill).as_posix())
             for path in sorted(skill.rglob('*'))
             if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc']
    files += [(ROOT / 'docs' / 'INSTALL.md', 'INSTALL.md'),
              (ROOT / 'LICENSE', 'LICENSE'),
              (ROOT / 'THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md')]
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED) as package:
        for source, name in files:
            package.write(source, name)
    with ZipFile(destination) as package:
        if package.testzip() is not None:
            raise ValueError('Package integrity check failed.')
        for source, name in files:
            if package.read(name) != source.read_bytes():
                raise ValueError(f'Package content mismatch: {name}')
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    checksum = destination.with_suffix('.zip.sha256')
    checksum.write_text(f'{digest}  {destination.name}\n', encoding='ascii')
    print(f'Packaged {len(files)} files: {destination}')
    print(f'SHA256: {digest}')


if __name__ == '__main__':
    main()
