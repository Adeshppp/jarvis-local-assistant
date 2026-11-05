"""SSD setup never lists a volume root. All application I/O uses anchored fds.

Reject symlinks rather than resolving a link into unapproved storage. openat with
O_NOFOLLOW on every component also closes the validation/open race.
"""
from __future__ import annotations
import contextlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import stat
import subprocess
import uuid

LAYOUT = ["models/llm", "models/speech_to_text", "models/text_to_speech",
          "models/wake_word", "models/embeddings", "model_cache", "document_index",
          "datasets", "backups", "archives", "logs", "temporary"]

class BoundaryError(PermissionError):
    pass

def disk_info(target: str) -> dict:
    p = subprocess.run(["/usr/sbin/diskutil", "info", "-plist", target],
                       capture_output=True, check=True, timeout=10)
    return plistlib.loads(p.stdout)

def initialize(record: Path, volume: str = "/Volumes/Sandisk") -> dict:
    if record.exists():
        raise BoundaryError("Storage already initialized; never create another SSD root")
    info = disk_info(volume)
    drive = disk_info(info["ParentWholeDisk"])
    if (info.get("Internal") or info.get("BusProtocol") != "USB"
            or "Extreme 55DD" not in (drive.get("MediaName", "") + drive.get("IORegistryEntryName", ""))
            or not 3.8e12 < drive.get("TotalSize", 0) < 4.2e12
            or not info.get("WritableVolume") or info.get("MountPoint") != volume):
        raise BoundaryError("Expected mounted 4 TB USB SanDisk Extreme 55DD")
    if not info.get("VolumeUUID"):
        raise BoundaryError("Missing persistent volume identity")
    mount = Path(volume)
    # No exists(), stat(), listdir(), or probing of an existing candidate.
    # mkdir is atomic and EEXIST is the only collision signal.
    for attempt in range(100):
        name = "Personal_AI_Assistant" if attempt == 0 else "Personal_AI_Assistant_" + uuid.uuid4().hex[:12]
        root = mount / name
        try:
            os.mkdir(root, 0o700)
            break
        except FileExistsError:
            continue
    else:
        raise BoundaryError("Cannot allocate a unique new root")
    binding = {"root": str(root.resolve(strict=True)), "volume": volume,
               "volume_uuid": info["VolumeUUID"], "filesystem": info.get("FilesystemType"),
               "binding_id": uuid.uuid4().hex, "created_new": True,
               "permissions_enforced_by_fs": bool(info.get("GlobalPermissionsEnabled"))}
    # Write the internal binding immediately so interrupted initialization cannot
    # accidentally create a second top-level directory on a retry.
    record.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(binding, f, indent=2)
    (root / ".assistant-binding.json").write_text(json.dumps(binding))
    for sub in LAYOUT:
        (root / sub).mkdir(parents=True, exist_ok=True, mode=0o700)
    return binding

class Root:
    def __init__(self, path: str | Path, binding: dict | None = None):
        self.path = Path(os.path.abspath(path))
        self.binding = binding

    @staticmethod
    def parts(relative: str) -> tuple[str, ...]:
        if not isinstance(relative, str) or not relative or "\x00" in relative or "\\" in relative:
            raise BoundaryError("Invalid relative path")
        p = PurePosixPath(relative)
        if p.is_absolute() or any(x in ("..", ".") for x in relative.split("/")):
            raise BoundaryError("Only paths inside an approved root are permitted")
        return p.parts

    def _anchor(self) -> int:
        if self.binding:
            info = disk_info(self.binding["volume"])
            if (info.get("VolumeUUID") != self.binding["volume_uuid"]
                    or info.get("MountPoint") != self.binding["volume"]):
                raise BoundaryError("SSD disconnected or replaced; access disabled")
        # The bound SSD path is recorded at creation and its mount UUID is checked
        # above. Open that root directly: never open or enumerate the SSD's root
        # directory even as an intermediate directory descriptor.
        if self.binding:
            if self.path.parent != Path(self.binding["volume"]) or not stat.S_ISDIR(os.lstat(self.path.parent).st_mode):
                raise BoundaryError("Unexpected mount or symlinked volume")
            fd = os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        else:
            fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            if not self.binding:
                for part in self.path.parts[1:]:
                    nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd)
                    fd = nxt
            if self.binding:
                marker = os.open(".assistant-binding.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                with os.fdopen(marker) as f:
                    actual = json.load(f)
                if actual.get("binding_id") != self.binding["binding_id"]:
                    raise BoundaryError("Wrong project directory; access disabled")
            return fd
        except BaseException:
            os.close(fd)
            raise

    @contextlib.contextmanager
    def parent(self, relative: str):
        parts = self.parts(relative)
        fd = self._anchor()
        try:
            for part in parts[:-1]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def read(self, relative: str, limit: int = 262144) -> bytes:
        with self.parent(relative) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, "rb") as f:
                s = os.fstat(f.fileno())
                if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
                    raise BoundaryError("Only regular, non-hardlinked files are supported")
                if s.st_size > limit:
                    raise BoundaryError("File exceeds read limit")
                return f.read(limit + 1)

    def write_new(self, relative: str, data: bytes):
        with self.parent(relative) as (parent, name):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, "wb") as f:
                f.write(data)

    def mkdir(self, relative: str):
        parts = self.parts(relative)
        fd = self._anchor()
        try:
            for name in parts:
                try: os.mkdir(name,0o700,dir_fd=fd)
                except FileExistsError: pass
                nxt = os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                os.close(fd); fd = nxt
        finally: os.close(fd)

    def runtime_path(self, relative: str) -> str:
        # Third-party libraries need filenames. Validate each component without
        # following links, then run those libraries under the SSD seatbelt profile.
        with self.parent(relative) as (parent,name):
            fd = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            os.close(fd)
        return str(self.path / relative)

    def names(self, relative: str, limit: int = 200) -> list[str]:
        with self.parent(relative) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                result = []
                with os.scandir(fd) as entries:
                    for e in entries:
                        if e.is_file(follow_symlinks=False):
                            result.append(e.name)
                        if len(result) >= limit:
                            break
                return result
            finally:
                os.close(fd)

def bound_root(record: Path) -> Root:
    b = json.loads(record.read_text())
    return Root(b["root"], b)
