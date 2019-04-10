import sys

HANDLE = None
if len(sys.argv) > 1:
    try:
        HANDLE = int(sys.argv[1])
    except ValueError:
        pass
