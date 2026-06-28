"""Import sources (optional). OneDrive lives here.

Like identification providers, sources are optional and lazily imported so the
base server stays lean. All network calls happen on-demand (browse/import), so
the idle-lightweight property is preserved.
"""
