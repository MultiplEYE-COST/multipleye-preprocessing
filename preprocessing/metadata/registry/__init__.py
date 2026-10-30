"""Field registrations for the codebook views."""

from __future__ import annotations

from collections.abc import Iterator

from preprocessing.metadata.schema import CodebookField

from . import dataset, item, participant, session, trial

__all__ = ["REGISTRY_FIELDS", "iter_registry_fields"]

REGISTRY_FIELDS = (
    *dataset.FIELDS,
    *session.FIELDS,
    *trial.FIELDS,
    *participant.FIELDS,
    *item.FIELDS,
)


def iter_registry_fields() -> Iterator[CodebookField]:
    """Yield all registered output fields."""
    yield from REGISTRY_FIELDS
