"""Manual labelling sidecar.

Stores human-applied verdict labels keyed by ``record_id`` in a
parquet sidecar, separate from the auto-extracted corpus. The
``package`` stage joins them in and lets manual labels override the
auto verdict so the pipeline stays fully resumable.
"""
