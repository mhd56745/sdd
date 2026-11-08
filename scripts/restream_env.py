#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restream_env.py — يحلل RESTREAM_URL ويطبع متغيرات shell جاهزة (بأسلوب export).

يُستدعى من entrypoint.sh هكذا:  eval "$(python3 restream_env.py)"

المخرجات:
    RESTREAM_ORIGIN     scheme://host  (لـ proxy_pass)
    RESTREAM_HOST       المضيف مع المنفذ (لترويسة Host)
    RESTREAM_TYPE       hls | ts
    RESTREAM_FULL_URL   الرابط الكامل (لبث TS المتواصل)
    RESTREAM_LINK       الرابط العام على محطتنا لصفحة المشغل
    RESTREAM_ENABLED    1 إذا كان الرابط مضبوطاً وإلا 0
"""

import os
import shlex
from urllib.parse import urlsplit

url = (os.environ.get("RESTREAM_URL") or "").strip()
force_type = (os.environ.get("RESTREAM_TYPE") or "auto").strip().lower()

if url:
    sp = urlsplit(url)
    scheme = sp.scheme or "https"
    netloc = sp.netloc
    path = sp.path or "/"
    query = ("?" + sp.query) if sp.query else ""

    rtype = force_type
    if rtype not in ("hls", "ts"):
        ext = path.lower().rsplit(".", 1)[-1]
        rtype = "ts" if ext in ("ts", "mts", "m2ts") else "hls"

    if rtype == "hls":
        link = "/restream" + path + query
    else:
        link = "/restream/stream.ts"

    values = {
        "RESTREAM_ORIGIN": "%s://%s" % (scheme, netloc),
        "RESTREAM_HOST": netloc,
        "RESTREAM_TYPE": rtype,
        "RESTREAM_FULL_URL": url,
        "RESTREAM_LINK": link,
        "RESTREAM_ENABLED": "1",
    }
else:
    values = {
        "RESTREAM_ORIGIN": "http://127.0.0.1:1",   # عنوان لا يُصل إليه عمداً
        "RESTREAM_HOST": "localhost",
        "RESTREAM_TYPE": force_type if force_type in ("hls", "ts") else "hls",
        "RESTREAM_FULL_URL": "http://127.0.0.1:1/stream.ts",
        "RESTREAM_LINK": "",
        "RESTREAM_ENABLED": "0",
    }

for key, val in values.items():
    print("export %s=%s" % (key, shlex.quote(val)))
