# SPDX-License-Identifier: MIT
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def valid_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("sources must use public HTTPS URLs without credentials")
    return url


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    data = data.encode() if isinstance(data, str) else data
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    fd, filename = tempfile.mkstemp(prefix=".spago-purifier-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(filename, path)
    finally:
        Path(filename).unlink(missing_ok=True)


def capture_git(repo, scratch):
    url = valid_url(repo["url"])
    rev = repo["commit"]
    if not re.fullmatch("[0-9a-f]{40}", rev):
        raise ValueError("native repository lacks an exact Git commit")
    checkout = Path(repo["directory"])
    actual = run(
        ["git", "-C", checkout, "rev-parse", "HEAD"], stdout=subprocess.PIPE, text=True
    ).stdout.strip()
    if actual != rev:
        raise ValueError("native registry repository moved during capture")
    target = scratch / ("repo-" + rev)
    target.mkdir(exist_ok=True)
    records = run(
        ["git", "-C", checkout, "ls-tree", "-r", "-z", "HEAD"], stdout=subprocess.PIPE
    ).stdout.split(b"\0")
    for record in records:
        if not record:
            continue
        header, filename = record.split(b"\t", 1)
        if header.split()[0] == b"160000":
            raise ValueError("registry repository submodules are not yet supported")
        relative = Path(os.fsdecode(filename))
        source, destination = checkout / relative, target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            if not destination.is_symlink():
                destination.symlink_to(os.readlink(source))
        else:
            shutil.copy2(source, destination)
    nar_hash = run(
        ["nix", "hash", "path", "--sri", target], stdout=subprocess.PIPE, text=True
    ).stdout.strip()
    return {
        "path": "repositories/" + repo["name"] + "/" + rev,
        "hash": nar_hash,
        "git": {
            "url": url,
            "rev": rev,
            "submodules": False,
            "leaveDotGit": False,
            "commitObject": None,
        },
    }
