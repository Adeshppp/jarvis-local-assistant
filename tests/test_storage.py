import json
import os
from pathlib import Path
import pytest
from assistant.storage import Root, BoundaryError

@pytest.fixture
def root(tmp_path):
    inside=tmp_path/"allowed";inside.mkdir()
    (inside/"folder").mkdir();(inside/"folder/file.txt").write_text("safe")
    return Root(inside)

@pytest.mark.parametrize("path",["../outside","folder/../../outside","/etc/passwd","folder/../file",".","folder/./file","folder\\file","", "bad\0name"])
def test_escaping_paths_rejected(root,path):
    with pytest.raises(BoundaryError):root.read(path)

def test_regular_io(root):
    assert root.read("folder/file.txt")==b"safe"
    root.write_new("folder/own.txt",b"new")
    with pytest.raises(FileExistsError):root.write_new("folder/own.txt",b"overwrite")
    assert root.read("folder/own.txt")==b"new"

def test_symlink_leaf_and_directory_rejected(root,tmp_path):
    # All fixtures are internal temporary files; never touch the actual SSD.
    outside=tmp_path/"outside";outside.mkdir();(outside/"secret").write_text("private")
    (root.path/"link").symlink_to(outside,target_is_directory=True)
    (root.path/"leaf").symlink_to(outside/"secret")
    for p in ("link/secret","leaf"):
        with pytest.raises(OSError):root.read(p)

def test_symlinked_root_rejected(root,tmp_path):
    alias=tmp_path/"alias";alias.symlink_to(root.path,target_is_directory=True)
    with pytest.raises(OSError):Root(alias).read("folder/file.txt")

def test_hardlink_and_fifo_rejected(root,tmp_path):
    f=tmp_path/"outside";f.write_text("secret")
    os.link(f,root.path/"hard")
    os.mkfifo(root.path/"fifo")
    for p in ("hard","fifo"):
        with pytest.raises(BoundaryError):root.read(p)

def test_volume_mismatch_rejected_before_any_file_open(root,monkeypatch):
    root.binding={"volume":"/fake","volume_uuid":"correct","binding_id":"expected"}
    monkeypatch.setattr("assistant.storage.disk_info",lambda _: {"VolumeUUID":"other","MountPoint":"/fake"})
    with pytest.raises(BoundaryError,match="disconnected or replaced"):root.read("folder/file.txt")

def test_marker_mismatch(root,monkeypatch):
    volume=str(root.path.parent)
    root.binding={"volume":volume,"volume_uuid":"correct","binding_id":"expected"}
    (root.path/".assistant-binding.json").write_text(json.dumps({"binding_id":"wrong"}))
    monkeypatch.setattr("assistant.storage.disk_info",lambda _: {"VolumeUUID":"correct","MountPoint":volume})
    with pytest.raises(BoundaryError,match="Wrong project"):root.read("folder/file.txt")

def test_bound_ssd_never_opens_volume_root(root,monkeypatch):
    volume=str(root.path.parent)
    root.binding={"volume":volume,"volume_uuid":"correct","binding_id":"expected"}
    (root.path/".assistant-binding.json").write_text(json.dumps({"binding_id":"expected"}))
    monkeypatch.setattr("assistant.storage.disk_info",lambda _: {"VolumeUUID":"correct","MountPoint":volume})
    calls=[];original=os.open
    def opened(path,*args,**kwargs):
        calls.append(str(path));return original(path,*args,**kwargs)
    monkeypatch.setattr(os,"open",opened)
    assert root.read("folder/file.txt")==b"safe"
    assert volume not in calls

def test_size_limits(root):
    with pytest.raises(BoundaryError):root.read("folder/file.txt",2)

def test_no_symlinks_created_by_mkdir(root,tmp_path):
    outside=tmp_path/"outside";outside.mkdir();(root.path/"link").symlink_to(outside)
    with pytest.raises(OSError):root.mkdir("link/new")
    assert not (outside/"new").exists()
