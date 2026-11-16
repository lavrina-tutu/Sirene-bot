"""Reproduce the binary elapsed-lag fixture, using POI already bundled by MPXJ.

No MPP writer is available in MPXJ. This changes one 20-byte constraint record
in a *copy* of the upstream Microsoft Project 2010 fixture. The stream layout is
specified by MPXJ ConstraintFactory (pinned upstream commit in manifest): UID +0,
predecessor UID +4, successor UID +8, type +12 (int16), units +14 (int16),
lag tenths of minutes +16 (int32). All values are little endian. MPP unit code
8 denotes elapsed days. -14400 tenths of minutes = -1 elapsed day.
"""
from pathlib import Path
import shutil
import struct


def make_elapsed_fixture(original, target):
    from read_mpp import _start_jvm
    _start_jvm()
    from java.io import File, ByteArrayInputStream
    from org.apache.poi.poifs.filesystem import POIFSFileSystem, DocumentInputStream
    shutil.copyfile(original, target)
    fs = POIFSFileSystem(File(str(Path(target).resolve())), False)
    try:
        directory = fs.getRoot().getEntry("   114").getEntry("TBkndCons")
        stream = DocumentInputStream(directory.getEntry("FixedData"))
        try:
            data = bytearray(bytes(stream.readAllBytes()))
        finally:
            stream.close()
        assert len(data) == 80
        assert struct.unpack_from("<iii", data, 20) == (2, 2, 3)
        assert struct.unpack_from("<hhi", data, 32) == (3, 7, 4800)
        struct.pack_into("<i", data, 16, 4800)  # FS +1 working day
        struct.pack_into("<hi", data, 34, 8, -14400)
        directory.createOrUpdateDocument("FixedData", ByteArrayInputStream(bytes(data)))
        fs.writeFilesystem()
    finally:
        fs.close()


def make_graph_fixture(original, target):
    """Keep a 2↔3 cycle; encode self 1→1 and dangling 99999→5 in raw MPP.

    The latter two are deliberately filtered by MPXJ ConstraintFactory. The
    exporter must retain an explicit unsupported raw-enumeration diagnostic.
    """
    from read_mpp import _start_jvm
    _start_jvm()
    from java.io import File, ByteArrayInputStream
    from org.apache.poi.poifs.filesystem import POIFSFileSystem, DocumentInputStream
    shutil.copyfile(original, target)
    fs = POIFSFileSystem(File(str(Path(target).resolve())), False)
    try:
        directory = fs.getRoot().getEntry("   114").getEntry("TBkndCons")
        stream = DocumentInputStream(directory.getEntry("FixedData"))
        try:
            data = bytearray(bytes(stream.readAllBytes()))
        finally:
            stream.close()
        assert len(data) == 80
        struct.pack_into("<ii", data, 4, 1, 1)
        struct.pack_into("<ii", data, 44, 3, 2)
        struct.pack_into("<ii", data, 64, 99999, 5)
        directory.createOrUpdateDocument("FixedData", ByteArrayInputStream(bytes(data)))
        fs.writeFilesystem()
    finally:
        fs.close()
