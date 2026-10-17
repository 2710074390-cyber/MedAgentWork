import olefile, struct, re, sys

path = "/workspace/.uploads/aed29292-32d8-4f43-ae74-65a216e11385_20261014耳鼻喉重点.doc"
ole = olefile.OleFileIO(path)
print("streams:", ole.listdir())

wd = ole.openstream('WordDocument').read()
print("WordDocument size:", len(wd))

# FIB
fcMin = struct.unpack('<I', wd[0x18:0x1C])[0]
fcMac = struct.unpack('<I', wd[0x1C:0x20])[0]
print("fcMin fcMac", fcMin, fcMac)

# determine which table stream
flags = struct.unpack('<H', wd[0x0A:0x0C])[0]
fWhichTblStm = (flags >> 9) & 1
tblname = '1Table' if fWhichTblStm else '0Table'
print("flags", hex(flags), "table stream", tblname)

# read CLX from table stream using fcClx/lcbClx at offset 0x01A2 in FIB (fibRgFcLcbBlob)
try:
    fcClx = struct.unpack('<I', wd[0x01A2:0x01A6])[0]
    lcbClx = struct.unpack('<I', wd[0x01A6:0x01AA])[0]
    print("fcClx lcbClx", fcClx, lcbClx)
    tbl = ole.openstream(tblname).read()
    clx = tbl[fcClx:fcClx+lcbClx]
    # parse CLX: skip Prc entries (0x01), find 0x02 Pcdt
    i = 0
    pcdt = None
    while i < len(clx):
        t = clx[i]
        if t == 0x01:
            cb = struct.unpack('<h', clx[i+1:i+3])[0]
            i += 3 + cb
        elif t == 0x02:
            lcb = struct.unpack('<I', clx[i+1:i+5])[0]
            pcdt = clx[i+5:i+5+lcb]
            break
        else:
            break
    print("pcdt len", len(pcdt) if pcdt else None)
    if pcdt:
        n = (len(pcdt) - 4) // 12
        cps = [struct.unpack('<I', pcdt[k*4:k*4+4])[0] for k in range(n+1)]
        pcds = pcdt[(n+1)*4:]
        out = []
        for k in range(n):
            pcd = pcds[k*8:k*8+8]
            fc = struct.unpack('<I', pcd[2:6])[0]
            fCompressed = (fc & 0x40000000) != 0
            fcReal = fc & 0x3FFFFFFF
            ln = cps[k+1] - cps[k]
            if fCompressed:
                fcReal = fcReal // 2
                chunk = wd[fcReal:fcReal+ln].decode('cp1252', 'replace')
            else:
                chunk = wd[fcReal:fcReal+ln*2].decode('utf-16-le', 'replace')
            out.append(chunk)
        text = ''.join(out)
        open('/workspace/_scratch/ent_raw.txt','w',encoding='utf-8').write(text)
        print("=== extracted chars:", len(text))
        print(text[:3000])
except Exception as e:
    print("PIECE TABLE FAIL:", e)
