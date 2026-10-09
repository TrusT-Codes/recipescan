"""Entry point: py -3 pipeline/run.py [extract|build|all]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recipescan.__main__ import main  # noqa: E402

sys.exit(main(sys.argv))
