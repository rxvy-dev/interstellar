import os

NAME = "Interstellar"
APP_ID = "io.github.interstellar.Terminal"
VERSION = "1.0.0"
REPO = "rxvy-dev/interstellar"          # GitHub owner/name — publish.sh updates this


def data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.path.join(here, "..", "data"), "/usr/share/interstellar/data", "/usr/local/share/interstellar/data",
              os.path.join(os.path.expanduser("~/.local/share"), "interstellar", "data")):
        d = os.path.normpath(d)
        if os.path.isdir(os.path.join(d, "icons")):
            return d
    return os.path.normpath(os.path.join(here, "..", "data"))
