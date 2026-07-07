import json
import logging
import threading
from pathlib import Path
from typing import Any

from filelock import FileLock

logger = logging.getLogger(__name__)
logging.getLogger("filelock").setLevel(logging.WARNING)


class JsonlCheckpointWriter:
    """
    Thread-safe append-only JSONL writer with resume support.

    Supports two modes:
      - Same-file mode: pass `path` — reads and writes happen in the same file.
      - Split mode: pass `in_path` (source records to process) and `out_path`
        (where results/checkpoints are appended). Use `load_remaining()` to
        get the keys from `in_path` that are NOT yet in `out_path`.

    Usage::

        # Same file (read completed keys + write to it)
        writer = JsonlCheckpointWriter(path="output.jsonl", key_field="id")
        done = writer.load_completed_keys()
        for item in items:
            if item["id"] in done:
                continue
            writer.write(process(item))

        # Split: read from in.jsonl, write checkpoints to out.jsonl
        writer = JsonlCheckpointWriter(in_path="input.jsonl", out_path="output.jsonl", key_field="id")
        remaining = writer.load_remaining()   # list of dicts from in_path not yet in out_path
        for item in remaining:
            writer.write(process(item))
    """

    def __init__(
        self,
        path: str | Path | None = None,
        in_path: str | Path | None = None,
        out_path: str | Path | None = None,
        key_field: str = "id",
    ):
        if path is not None and (in_path is not None or out_path is not None):
            raise ValueError(
                "Pass either `path` alone, or `in_path`/`out_path` — not both."
            )
        if path is None and out_path is None:
            raise ValueError("Must provide either `path` or `out_path`.")

        self.key_field = key_field
        self._lock = threading.Lock()

        self.in_path = Path(in_path) if in_path else (Path(path) if path else None)
        self.out_path = Path(out_path) if out_path else Path(path)

        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.out_path.touch(exist_ok=True)

        self._file_lock = FileLock(str(self.out_path) + ".lock")

    def load_completed_keys(self) -> set[str]:
        """
        Read the out_path file, return the set of keys already processed.
        """
        keys = set()
        for record in self._read_jsonl(self.out_path):
            try:
                keys.add(record[self.key_field])
            except KeyError:
                continue

        logger.info(f"Found {len(keys)} completed keys!")
        return keys

    def load_remaining_keys(self) -> list[str]:
        """
        Read in_path, return the list of keys of source records whose key is NOT
        already present in out_path (i.e. not yet completed).

        Requires `in_path` to have been provided.
        """
        remaining = self.load_remaining()
        return [record[self.key_field] for record in remaining]

    def load_remaining(self) -> list[dict[str, Any]]:
        """
        Read in_path, return the list of source records whose key is NOT
        already present in out_path (i.e. not yet completed).

        Note: Does NOT deduplicate according to ``self.key_field``!

        Requires `in_path` to have been provided.
        """
        if self.in_path is None:
            raise ValueError(
                "load_remaining() requires `in_path` (or `path`) to be set."
            )

        done = self.load_completed_keys()
        remaining = []
        for record in self._read_jsonl(self.in_path):
            key = record.get(self.key_field)
            if key is None or key not in done:
                remaining.append(record)
        return remaining

    def write(self, records: list[dict[str, Any]] | dict[str, Any]) -> None:
        """
        Append records to out_path.
        """
        items = records if isinstance(records, list) else [records]
        with self._lock:
            with self._file_lock:
                with self.out_path.open("a") as f:
                    for item in items:
                        if item is not None:
                            f.write(json.dumps(item, default=str) + "\n")
                    f.flush()

    @staticmethod
    def _read_jsonl(p: Path) -> list[dict[str, Any]]:
        records = []
        if not p.exists():
            return records
        with p.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # tolerate a truncated last line from a crash mid-write
                    continue
        return records
