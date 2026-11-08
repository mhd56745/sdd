#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mp4_info.py — قراءة مدة الملف والترميزات مباشرة من ذرات MP4 (بدون ffmpeg نهائياً).

يعيد dict بالشكل:
    {
        "duration_ms": <int>,          # أقصر مدة بين المسارات (نفس منطق ffprobe في المثال المرجعي)
        "video": "avc1" | None,        # ترميز الفيديو الأساسي
        "audio": "mp4a" | None,        # ترميز الصوت الأساسي
    }

يدعم:
- صندوق moov في أي مكان بالملف (بداية أو نهاية) عبر القراءة العشوائية (لا يقرأ الملف كاملاً).
- أحجام 64-بت (size == 1) والحجم صفر (آخر الملف).
- نسختي mvhd/mdhd (32/64-بت).
"""

import os
import struct

VIDEO_OK = {"avc1", "avc3"}          # H.264
VIDEO_KNOWN = VIDEO_OK | {"hev1", "hvc1", "hvc9"}  # H.265 غير مدعوم في TS
AUDIO_KNOWN = {"mp4a", "mp3 ", ".mp3", "ac-3", "ec-3", "opus", "fLaC"}


def _iter_boxes(f, start, end):
    """يمرّ على الصندوق المباشرة بين start و end في ملف مفتوح."""
    off = start
    while off + 8 <= end:
        f.seek(off)
        hdr = f.read(16)
        if len(hdr) < 8:
            break
        size, btype = struct.unpack_from(">I4s", hdr, 0)
        hlen = 8
        if size == 1:
            if len(hdr) < 16:
                break
            size = struct.unpack_from(">Q", hdr, 8)[0]
            hlen = 16
        elif size == 0:
            size = end - off
        if size < hlen or off + size > end:
            break
        yield btype, off + hlen, off + size
        off += size


def _find_box(f, start, end, wanted):
    for btype, bs, be in _iter_boxes(f, start, end):
        if btype == wanted:
            return bs, be
    return None


def _parse_fullbox_header(f, box_start):
    """يقرأ version+flags (4 بايت) من بداية محتوى الصندوق ويعيد الإزاحة بعد الترويسة."""
    f.seek(box_start)
    ver = f.read(1)[0]
    return ver, box_start + 4


def _read_mdhd(f, s, e):
    """يرجع (timescale, duration) من صندوق mdhd."""
    if s is None:
        return None
    ver, p = _parse_fullbox_header(f, s)
    if ver == 1:
        f.seek(p + 16)  # creation+modification (8+8)
        ts, dur = struct.unpack(">IQ", f.read(12))
    else:
        f.seek(p + 8)   # creation+modification (4+4)
        ts, dur = struct.unpack(">II", f.read(8))
    return ts, dur


def probe(path):
    """يحلل ملف MP4/MOV ويعيد المدة والترميزات، أو يرفع استثناء عند فشل التحليل."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        moov = _find_box(f, 0, size, b"moov")
        if moov is None:
            raise ValueError("لا يوجد صندوق moov")

        mvhd = _find_box(f, moov[0], moov[1], b"mvhd")
        mv = _read_mdhd(f, mvhd[0], mvhd[1]) if mvhd else None

        durations = []
        if mv and mv[0] and mv[1]:
            durations.append(float(mv[1]) / mv[0])

        video = None
        audio = None

        # المرور على كل المسارات
        pos = moov
        while True:
            trak = _find_box(f, pos[0], pos[1], b"trak")
            if trak is None:
                break
            mdia = _find_box(f, trak[0], trak[1], b"mdia")
            if mdia:
                mdhd = _find_box(f, mdia[0], mdia[1], b"mdhd")
                md = _read_mdhd(f, mdhd[0], mdhd[1]) if mdhd else None
                if md and md[0] and md[1]:
                    durations.append(float(md[1]) / md[0])
                minf = _find_box(f, mdia[0], mdia[1], b"minf")
                if minf:
                    stbl = _find_box(f, minf[0], minf[1], b"stbl")
                    if stbl:
                        stsd = _find_box(f, stbl[0], stbl[1], b"stsd")
                        if stsd:
                            # fullbox: version+flags (4) + entry_count (4)
                            f.seek(stsd[0] + 8)
                            raw = f.read(8)
                            if len(raw) == 8:
                                entry_size, fmt = struct.unpack(">I4s", raw)
                                if 8 <= entry_size <= stsd[1] - stsd[0]:
                                    tag = fmt.decode("latin-1")
                                    if tag in VIDEO_OK:
                                        video = "avc1"
                                    elif tag in VIDEO_KNOWN:
                                        video = video or tag
                                    elif tag in AUDIO_KNOWN:
                                        audio = tag.strip() if audio is None else audio
            pos = (trak[1], moov[1])

        if not durations:
            raise ValueError("لا توجد مدة صالحة")

        duration_ms = int(min(durations) * 1000)
        return {
            "duration_ms": duration_ms,
            "video": video,
            "audio": audio,
        }


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:]:
        try:
            print(p, probe(p))
        except Exception as exc:  # noqa: BLE001
            print(p, "ERROR:", exc)
