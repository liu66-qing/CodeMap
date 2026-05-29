"""Git history loader: walk a repository's commits and parse each snapshot.

This is the engine behind the "code documentary" capability — the thing a
static analyzer like GitNexus structurally cannot do. For every commit we
reconstruct the code graph *as it existed at that point in time*, which lets the
downstream layers answer "how did this function evolve?" and "which commit
introduced a breaking change?".

Implementation notes:
- Uses plain `git` via subprocess (no GitPython dependency) so it works
  anywhere git is installed.
- Reads file contents with `git show <rev>:<path>` instead of checking out, so
  it never mutates the working tree and is safe to run on a live repo.
- Parsing reuses the deterministic `code_parser`, so a "snapshot" is just a
  list of ParseResult — the same structure the rest of the pipeline consumes.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

from evograph.ingestion.code_parser import parse_python_source, ParseResult


@dataclass
class CommitInfo:
    sha: str
    short_sha: str
    author: str
    email: str
    timestamp: datetime
    subject: str
    parent_sha: str = ""   # first parent; empty for the root commit


@dataclass
class CommitSnapshot:
    commit: CommitInfo
    parses: list[ParseResult] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)  # .py paths touched by this commit


class GitHistoryError(RuntimeError):
    pass


def _run_git(repo_path: str, args: list[str], binary: bool = False) -> str | bytes:
    """Run a git command in repo_path and return stdout (text by default)."""
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:  # git not installed
        raise GitHistoryError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", "replace") if exc.stderr else ""
        raise GitHistoryError(f"git {' '.join(args)} failed: {stderr.strip()}") from exc
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def list_commits(repo_path: str, max_commits: int | None = None, branch: str = "HEAD") -> list[CommitInfo]:
    """Return commits oldest-first (chronological), so replaying them models
    forward evolution through time."""
    # Unit-separated fields, record-separated rows, to survive odd commit text.
    fmt = "%H%x1f%h%x1f%an%x1f%ae%x1f%aI%x1f%s%x1f%P"
    args = ["log", f"--pretty=format:{fmt}", branch]
    if max_commits:
        args.insert(1, f"-n{max_commits}")
    out = _run_git(repo_path, args)
    commits: list[CommitInfo] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) < 6:
            continue
        sha, short, author, email, iso, subject = parts[:6]
        parents = parts[6].split() if len(parts) > 6 and parts[6].strip() else []
        first_parent = parents[0] if parents else ""
        try:
            ts = datetime.fromisoformat(iso)
        except ValueError:
            ts = datetime.now(timezone.utc)
        commits.append(
            CommitInfo(sha=sha, short_sha=short, author=author, email=email,
                       timestamp=ts, subject=subject, parent_sha=first_parent)
        )
    commits.reverse()  # oldest first
    if max_commits:
        commits = commits[-max_commits:]
    return commits


def _list_py_blobs_at(repo_path: str, rev: str) -> list[tuple[str, str]]:
    """Return (blob_sha, path) for every .py file tracked at a given revision.

    The blob SHA is git's content hash: two files (across commits or paths) with
    identical bytes share a blob SHA. That identity is what lets us parse each
    distinct file content exactly once instead of once per commit.
    """
    # Without --name-only, ls-tree emits: "<mode> <type> <sha>\t<path>".
    out = _run_git(repo_path, ["ls-tree", "-r", rev])
    blobs: list[tuple[str, str]] = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        if not path.endswith(".py"):
            continue
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        blobs.append((parts[2], path))
    return blobs


def _read_file_at(repo_path: str, rev: str, path: str) -> str | None:
    """File contents at a revision, or None if unreadable/binary.

    Kept as a single-file convenience; the history walk uses the batched
    `_batch_read_blobs` path instead to avoid a subprocess per file.
    """
    try:
        raw = _run_git(repo_path, ["show", f"{rev}:{path}"], binary=True)
    except GitHistoryError:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _batch_read_blobs(repo_path: str, shas: list[str]) -> dict[str, str | None]:
    """Read many blobs in ONE `git cat-file --batch` call.

    Returns {blob_sha: decoded_text or None}. None means the blob is missing or
    not valid UTF-8 (e.g. binary). An empty input list spawns no subprocess.

    This collapses what used to be one `git show` per file into a single git
    invocation per commit — the main lever against the subprocess storm.
    """
    if not shas:
        return {}
    # Feed all OIDs via stdin; subprocess.run handles the write/read concurrency
    # internally (communicate), so a full pipe buffer can't deadlock us.
    stdin = ("\n".join(shas) + "\n").encode("utf-8")
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, "cat-file", "--batch"],
            input=stdin,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise GitHistoryError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", "replace") if exc.stderr else ""
        raise GitHistoryError(f"git cat-file --batch failed: {stderr.strip()}") from exc

    data = proc.stdout
    out: dict[str, str | None] = {}
    i, n = 0, len(data)
    while i < n:
        # Each record starts with a header line: "<sha> <type> <size>\n"
        # or, for an unknown object, "<sha> missing\n".
        nl = data.find(b"\n", i)
        if nl == -1:
            break
        header = data[i:nl].decode("utf-8", "replace").split()
        i = nl + 1
        if len(header) == 2 and header[1] == "missing":
            out[header[0]] = None
            continue
        if len(header) < 3:
            break
        sha, size = header[0], int(header[2])
        content = data[i : i + size]
        i += size + 1  # skip the trailing newline git appends after content
        try:
            out[sha] = content.decode("utf-8")
        except UnicodeDecodeError:
            out[sha] = None
    return out


def _changed_py_files(repo_path: str, rev: str) -> list[str]:
    """.py files changed by this commit relative to its first parent.
    For the root commit (no parent), returns all .py files."""
    try:
        out = _run_git(
            repo_path,
            ["diff-tree", "--no-commit-id", "--name-only", "-r", rev],
        )
    except GitHistoryError:
        return []
    return [p for p in out.splitlines() if p.endswith(".py")]


def _module_name(path: str, src_prefixes: tuple[str, ...]) -> str:
    """Turn a repo-relative file path into a dotted module name, stripping a
    leading src/-style prefix so module names match across the project."""
    p = path
    for prefix in src_prefixes:
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    if p.endswith(".py"):
        p = p[:-3]
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    return p.strip("/").replace("/", ".")


def load_commit_snapshot(
    repo_path: str,
    commit: CommitInfo,
    src_prefixes: tuple[str, ...] = ("src/", "lib/"),
    max_files: int | None = None,
    parse_cache: dict[tuple[str, str], ParseResult] | None = None,
) -> CommitSnapshot:
    """Parse every .py file as it existed at `commit`.

    `parse_cache` maps (blob_sha, path) -> ParseResult and is shared across
    commits by `iter_history`. A blob SHA uniquely identifies file content, so
    an unchanged file (same content at the same path) is parsed exactly once for
    the entire history instead of once per commit. We include the path in the
    key because the parser derives module/qualified names from it — the same
    blob at a different path (e.g. after a rename) must be parsed under its new
    module name, not reused. Cached ParseResults are treated as read-only by all
    consumers (the adapter and the breaking-change detector only read them), so
    sharing one object across snapshots is safe.
    """
    cache = parse_cache if parse_cache is not None else {}
    blobs = _list_py_blobs_at(repo_path, commit.sha)
    if max_files:
        blobs = blobs[:max_files]

    # Only fetch blobs whose (sha, path) we haven't parsed yet.
    missing = sorted({sha for sha, path in blobs if (sha, path) not in cache})
    contents = _batch_read_blobs(repo_path, missing)

    parses: list[ParseResult] = []
    for sha, path in blobs:
        cached = cache.get((sha, path))
        if cached is not None:
            parses.append(cached)
            continue
        source = contents.get(sha)
        if source is None:
            continue
        module = _module_name(path, src_prefixes)
        result = parse_python_source(source, module, path)
        cache[(sha, path)] = result
        parses.append(result)

    changed = _changed_py_files(repo_path, commit.sha)
    return CommitSnapshot(commit=commit, parses=parses, changed_files=changed)


def iter_history(
    repo_path: str,
    max_commits: int | None = None,
    branch: str = "HEAD",
    src_prefixes: tuple[str, ...] = ("src/", "lib/"),
    max_files: int | None = None,
):
    """Yield CommitSnapshot for each commit, oldest first.

    A single (blob, path)->ParseResult cache is shared across the whole walk, so
    files that don't change between commits are parsed only once. This turns the
    cost from O(commits × files) down to O(distinct file versions).
    """
    parse_cache: dict[tuple[str, str], ParseResult] = {}
    for commit in list_commits(repo_path, max_commits=max_commits, branch=branch):
        yield load_commit_snapshot(
            repo_path,
            commit,
            src_prefixes=src_prefixes,
            max_files=max_files,
            parse_cache=parse_cache,
        )

