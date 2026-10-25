"""Small frozen GUI entry point; capture and extraction run in the console worker."""

import sys

from majsoul_hook.gui import main

if __name__ == "__main__":
    main(smoke_test=sys.argv[1:] == ["--smoke-test"])
