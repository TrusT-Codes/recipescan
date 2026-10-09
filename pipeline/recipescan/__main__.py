"""recipescan data pipeline.

    py -3 pipeline/run.py extract   read reference addons -> data/extracted/*.json
    py -3 pipeline/run.py build     data/*.txt + data/extracted -> build/recipescan.sqlite, web/public/data/*.json, build/report.md
    py -3 pipeline/run.py all       both
"""
import sys


def main(argv):
    stage = argv[1] if len(argv) > 1 else 'build'
    if stage not in ('extract', 'build', 'all'):
        print(__doc__)
        return 2
    if stage in ('extract', 'all'):
        from . import extract
        extract.run()
    if stage in ('build', 'all'):
        from . import build
        build.run()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
