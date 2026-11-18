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


def make_identity_positive_fixture(original, target, *, revision=False):
    """Binary-only supported fixture, from pinned upstream mpp14relations.

    Promote the stored project-summary row to content summary UID 1000 / ID 1;
    shift leaf row IDs/outline levels, preserving UID identities and dates.
    Pinned FieldMap14 layout: task ID +4, parent UID +36, outline int16 +40;
    task FixedMeta header 16, row 47, FixedData offset +4. No JSON export is
    edited. Keep four ordinary FS links, working-day lag 0; the revised source
    has a one-day FS lag on UID 1 for a source-addressed test exclusion.
    """
    from read_mpp import _start_jvm
    _start_jvm()
    from java.io import File, ByteArrayInputStream
    from org.apache.poi.poifs.filesystem import POIFSFileSystem, DocumentInputStream
    import hashlib
    assert hashlib.sha256(Path(original).read_bytes()).hexdigest() == '8f33cdb774aa090b664d90145879acc8a289057ca45a6575884eb0da9fd91f30'
    shutil.copyfile(original,target)
    fs=POIFSFileSystem(File(str(Path(target).resolve())),False)
    try:
        project=fs.getRoot().getEntry('   114')
        tasks=project.getEntry('TBkndTask')
        def read(directory,name):
            stream=DocumentInputStream(directory.getEntry(name))
            try:return bytearray(bytes(stream.readAllBytes()))
            finally:stream.close()
        meta=read(tasks,'FixedMeta');data=read(tasks,'FixedData')
        assert len(meta)==439 and len(data)==1284
        changed=[]
        for i in range((len(meta)-16)//47):
            offset=struct.unpack_from('<i',meta,16+i*47+4)[0]
            uid,ident=struct.unpack_from('<ii',data,offset)
            if uid<0:continue
            assert uid==ident and 0<=uid<=5
            level=struct.unpack_from('<h',data,offset+40)[0]
            assert level==(0 if uid==0 else 1)
            if uid==0:
                struct.pack_into('<i',data,offset,1000)
            else:
                assert struct.unpack_from('<i',data,offset+36)[0]==0
                struct.pack_into('<i',data,offset+36,1000)
            struct.pack_into('<i',data,offset+4,ident+1)
            struct.pack_into('<h',data,offset+40,level+1)
            # Deliberately build a duration-only source fixture: FixedDuration,
            # no effort-driven scheduling and no source work/progress.
            struct.pack_into('<h',data,offset+94,1)
            struct.pack_into('<ddd',data,offset+126,0.0,0.0,0.0)
            meta[16+i*47+11] &= ~0x10
            changed.append(uid)
        assert changed==list(range(6))
        tasks.createOrUpdateDocument('FixedMeta',ByteArrayInputStream(bytes(meta)))
        tasks.createOrUpdateDocument('FixedData',ByteArrayInputStream(bytes(data)))
        # VarMeta12: 24-byte header, 12-byte entries, task UID at +0.
        # MPXJ renumbers IDs from 0 if UID 0 exists, hence the explicit UID remap.
        varmeta=read(tasks,'VarMeta')
        assert (len(varmeta)-24)%12==0
        for offset in range(24,len(varmeta),12):
            if struct.unpack_from('<i',varmeta,offset)[0]==0:
                struct.pack_into('<i',varmeta,offset,1000)
        tasks.createOrUpdateDocument('VarMeta',ByteArrayInputStream(bytes(varmeta)))
        # Empty assignment streams in the binary source, not a cleaned export.
        # Preserve the original valid stream headers; counts/data sizes become 0.
        assn=project.getEntry('TBkndAssn')
        for name,header in [('FixedMeta',16),('Fixed2Meta',16),('VarMeta',24)]:
            if assn.hasEntry(name):
                block=read(assn,name)[:header]
                if len(block)>=12:struct.pack_into('<i',block,8,0)
                if len(block)>=24:struct.pack_into('<i',block,20,0)
                assn.createOrUpdateDocument(name,ByteArrayInputStream(bytes(block)))
        for name in ['FixedData','Fixed2Data','Var2Data']:
            if assn.hasEntry(name):assn.createOrUpdateDocument(name,ByteArrayInputStream(b''))
        cons=project.getEntry('TBkndCons');links=read(cons,'FixedData');assert len(links)==80
        for offset in range(0,len(links),20):
            struct.pack_into('<hhi',links,offset+12,1,7,4800 if revision and offset==0 else 0)
        cons.createOrUpdateDocument('FixedData',ByteArrayInputStream(bytes(links)))
        fs.writeFilesystem()
    finally:fs.close()
