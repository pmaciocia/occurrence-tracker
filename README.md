# Occurrence Tracker

[![hacs][hacs-badge]][hacs-url]

A small Home Assistant integration for a question core can't answer: **when does
this usually happen?**

Core's `statistics` and `history_stats`, and the HACS `historical_stats`, all
aggregate over a *contiguous window* — "this week", "3 months ago", "all
history". None of them fold occurrences back onto a repeating cycle, so there is
no built-in way to ask "what hour of the day is this most likely?" or "is it
mostly a weekend thing?". Jinja templates can't help either: they have no access
to the recorder or the statistics tables.

This integration answers it by recording the events itself.

It's aimed at things that happen **occasionally** — once or twice a week — where
the recorder's ~10-day retention means raw history has nothing useful in it, and
where you want the pattern rather than the log.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/pmaciocia/occurrence-tracker` with category
   **Integration**
3. Find **Occurrence Tracker** in HACS and download it
4. Restart Home Assistant

### Manual

Copy `custom_components/occurrence_tracker/` into your `config/custom_components/`
directory so you end up with
`config/custom_components/occurrence_tracker/manifest.json`, then restart.

### Set it up

**Settings → Devices & Services → Helpers → Create helper → Occurrence Tracker**,
then give it a name. Add as many as you like — each gets its own device and its
own stored history.

Deleting a config entry deletes its recorded occurrences too, so nothing is left
orphaned in `.storage`.

## What it creates

One config entry, one device, five entities. With the entry named *Last*:

| Entity | What it is |
|---|---|
| `button.last_record` | Press when the thing happens. |
| `sensor.last_total` | Running total. Its `statistic_id` attribute names the long-term statistic (`occurrence_tracker:last`) that date-based charts should read — see [Long-term statistics](#long-term-statistics). |
| `sensor.last_last` | Timestamp of the most recent occurrence. |
| `sensor.last_by_hour` | State is the busiest hour (`"14:00"`). Attributes carry the full 24-hour profile. |
| `sensor.last_by_weekday` | State is the busiest day (`"Saturday"`). Attributes carry the full 7-day profile. |

Both profile sensors expose their distribution three ways:

```yaml
profile: [{hour: 0, count: 0}, {hour: 1, count: 2}, ...]   # for chart cards
counts:  [0, 2, 0, ...]                                     # for templates
total:   14
```

`by_weekday`'s profile entries are `{day: 1..7, name: "Monday", count: n}`,
Monday first.

## The design decision that matters

**It stores raw timestamps, not buckets.** Every occurrence is kept in
`.storage` as a UTC timestamp; the hour and weekday profiles are computed from
that list on demand.

At the volumes this is built for — a couple of events a week, so a few hundred a
year — the list is trivially small, and keeping the source data means the
bucketing is never a decision you're locked into. Two-hourly blocks,
weekday-versus-weekend, month of year: all of it can be added later and will
apply to everything already recorded. A design built on counters throws that
away at the moment of recording and can never get it back.

The long-term statistics the integration writes are a *projection* of that list
— derived from it on every change — never a substitute for it.

Bucketing happens in **local time** via `dt_util.as_local`, so an event at 23:30
UTC in July lands in the 00:00 bucket of the following day, as it should. This
is the part that makes the obvious alternative — querying the recorder database
with SQL — awkward, because MariaDB needs its timezone tables loaded to do the
same conversion and a fixed offset silently breaks across BST.

## Services

All three target the button entity.

| Service | Purpose |
|---|---|
| `occurrence_tracker.record` | Record an occurrence. The optional `timestamp` field records one in the **past** — the backfill path for events you remember but never logged. |
| `occurrence_tracker.remove_last` | Undo the most recent occurrence, for an accidental press. |
| `occurrence_tracker.clear` | Forget everything. Not undoable. |

```yaml
action: occurrence_tracker.record
target:
  entity_id: button.last_record
data:
  timestamp: "2026-09-01 14:30:00"
```

| `occurrence_tracker.rebuild_statistics` | Rewrites the long-term statistics from the stored timestamps. Only needed if the two drift — a database restored from an older backup, say. |

Removing an occurrence is a real correction: the long-term statistics are
rewritten from the remaining timestamps, so the count goes down everywhere.

## Charting the profiles

The `profile` attribute is shaped for the
[Statistics Graph Chart Card](https://github.com/cataseven/Statistics-Graph-Chart-Card)'s
attribute data source:

```yaml
type: custom:statistics-graph-chart-card
card_header: By hour of day
chart_mode: timeline
group_by: hour
entities:
  - entity: sensor.last_by_hour
    data_attribute: profile
    data_time_field: hour
    data_value_field: count
    data_time_unit: hour_of_day
    graph_type: bar
    aggregate_func: max
    decimals: 0
```

That card has no `day_of_week` time unit, so the weekday profile is better drawn
from `counts` by any card that can plot a plain list, or read straight off the
sensor's state ("busiest day").

## Long-term statistics

Every tracker also writes an **external statistic** — `occurrence_tracker:last`
for a tracker named *Last* — into Home Assistant's long-term statistics. That is
what drives ordinary date-based charts: a day × hour heatmap, a GitHub-style
year calendar, a weekly count. Point the card at the statistic id rather than at
an entity:

```yaml
type: custom:statistics-graph-chart-card
chart_mode: heatmap
group_by: hour
hours_to_show: 2160
entities:
  - statistic_id: occurrence_tracker:last
    aggregate_func: change
```

HA's built-in statistics-graph card reads the same id. The id is fixed when the
tracker is first set up and shown in `sensor.*_total`'s `statistic_id`
attribute; renaming the tracker afterwards doesn't change it.

### Why not just a `total_increasing` sensor?

Because the recorder compiles a sensor's statistics from its *state
transitions*, and a transition doesn't say what it means. Two things go wrong:

- **Backfills land on the wrong day.** Recording something that happened in
  July changes the sensor's state *now*, so the recorder books it now.
- **Removals double-count.** `total_increasing` reads any drop below 90% of the
  previous value as a meter reset and starts a fresh cycle from the new value.
  Removing one of five occurrences yields a sum of *nine*, not four.

An external statistic has no sensor behind it. The integration owns the rows and
writes them from the timestamps it holds, so a backfilled occurrence sits on the
hour it happened and a removal genuinely subtracts. The rows are sparse — one per
hour that has an occurrence, carrying the cumulative total — and Home Assistant
derives the count in any period as `sum(end) − sum(start)`, so per-hour,
per-day and per-month figures all come out right.

**The timestamps remain the source of truth.** The statistics are a projection
of them, rebuilt from them, never the other way round. If the two ever disagree
— after restoring an older database backup, say — `rebuild_statistics` puts the
statistics back in line with the timestamps.

## Requirements

Home Assistant 2025.4.0 or newer (for `StatisticMeanType` in the statistics API).

## License

MIT

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
