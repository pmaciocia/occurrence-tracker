"""Pure helpers that turn occurrence timestamps into statistics rows.

Deliberately free of Home Assistant imports so the arithmetic can be unit-tested
anywhere. Everything here is a function of the timestamp list and nothing else,
which is the property that keeps the statistics and the stored timestamps from
ever disagreeing: the rows are derived, never maintained.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import re
import unicodedata

_NON_SLUG = re.compile(r"[^a-z0-9]+")

# One statistics row: the UTC start of an hour, and the running total of
# occurrences up to and including that hour.
Row = tuple[datetime, int]


def statistic_object_id(title: str) -> str:
    """Reduce a config entry title to the object part of a statistic id.

    Home Assistant requires ``[a-z0-9_]`` with no leading, trailing or doubled
    underscores. Accented letters are folded to their base letter first so
    "Café" becomes ``cafe`` rather than ``caf``; runs of anything else collapse
    to one underscore.
    """
    ascii_title = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    )
    slug = _NON_SLUG.sub("_", ascii_title.lower()).strip("_")
    return slug or "tracker"


def hour_floor(when: datetime) -> datetime:
    """The UTC start of the hour containing ``when``.

    Statistics rows live in UTC. The by-hour and by-weekday profiles bucket in
    local time; those are two different bucketings on purpose, and neither is
    derived from the other.
    """
    return when.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def build_rows(timestamps: Iterable[datetime]) -> list[Row]:
    """Build the sparse, ascending row list for a set of occurrences.

    Only hours with at least one occurrence get a row. Each row's total is
    cumulative, which is what Home Assistant's ``sum`` column means: it derives
    the count in any period as ``sum(end) - sum(start)``, so a sparse series
    still yields the right per-hour, per-day and per-month counts.
    """
    rows: list[Row] = []
    total = 0
    for when in sorted(timestamps):
        hour = hour_floor(when)
        total += 1
        if rows and rows[-1][0] == hour:
            rows[-1] = (hour, total)
        else:
            rows.append((hour, total))
    return rows


def rows_from(rows: list[Row], hour: datetime) -> list[Row]:
    """The rows at or after ``hour`` — the ones an edit at that hour invalidates.

    Because totals are cumulative, inserting an occurrence shifts every later
    row's total by one, so all of them must be rewritten, not just the hour
    the occurrence landed in.
    """
    return [row for row in rows if row[0] >= hour]
