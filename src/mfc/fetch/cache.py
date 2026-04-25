"""On-disk HTTP response cache.

Implemented as a ``hishel`` storage backed by the local filesystem under
``data/raw/``. Hishel honours HTTP cache semantics (``If-Modified-Since``,
``ETag``, ``Cache-Control``) and serializes responses with msgpack rather
than pickle, so a cache file cannot trigger code execution on read.
"""
