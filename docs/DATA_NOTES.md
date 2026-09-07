# Data notes

Every decision that had to be made about a source file is written down here.
Raw files are never edited. Where a published layout did not match what a loader
expected, the loader was changed and the change recorded below.

## Geography

### Why upper tier

Adult social care and children's services are run by upper tier authorities. In
Office for National Statistics coding those are unitary authorities (E06),
metropolitan districts (E08), London boroughs (E09) and county councils (E10).
Together they are the 153 councils that appear in the client level data. Lower
tier districts (E07) do not run social care and are excluded everywhere in this
repository by the `UPPER_TIER_PATTERN` filter in `src/loaders.py`.

### Deprivation file

The project specification named File 10 of the English indices of deprivation
2019, which is the lower tier district summary. File 11 is used instead, because
it is published at upper tier, which is the geography social care is run at.
Using File 10 would have meant aggregating district scores into counties with a
population weighting that the publisher does not endorse. Both files are
downloaded, so File 10 remains available for any later district level work.

The URL given for File 10 in the specification returned a 404. The current URL
was taken from the publication page and both are recorded in
`scripts/download.py`.

### Boundary files

The specification named the Local Authority Districts May 2024 ultra generalised
boundaries. That layer has 361 features and is district level, so it cannot draw
a map of the 153 councils that run social care. The Counties and Unitary
Authorities December 2023 layer is used for the choropleths, and it matches the
boundaries the mid-2024 population estimates are published on. The district layer
is still downloaded and is available through
`loaders.load_boundaries(upper_tier=False)`.

Both layers come from an ArcGIS feature service, which caps how many features it
returns in one response. `scripts/download.py` follows the paging and writes a
single GeoJSON FeatureCollection.

## Local government reorganisation

Six areas reorganised between 2019 and 2023, and the Office for National
Statistics reissued codes for two metropolitan districts. `src/geography.py`
translates every source onto one set of codes before anything is joined.

### One old code to one new code

| Old code | Old name | New code | New name | Year |
| --- | --- | --- | --- | --- |
| E06000028 | Bournemouth | E06000058 | Bournemouth, Christchurch and Poole | 2019 |
| E06000029 | Poole | E06000058 | Bournemouth, Christchurch and Poole | 2019 |
| E10000009 | Dorset county council | E06000059 | Dorset unitary authority | 2019 |
| E10000002 | Buckinghamshire county council | E06000060 | Buckinghamshire unitary authority | 2020 |
| E10000023 | North Yorkshire county council | E06000065 | North Yorkshire unitary authority | 2023 |
| E10000027 | Somerset county council | E06000066 | Somerset unitary authority | 2023 |
| E08000038 | Barnsley | E08000016 | Barnsley | code reissue |
| E08000039 | Sheffield | E08000019 | Sheffield | code reissue |

The Barnsley and Sheffield entries are not reorganisations. The Department for
Education uses newer codes for those two districts in its 2025 tables than the
Office for National Statistics uses in the mid-2024 population estimates, so the
newer codes are mapped back to the ones the population file uses.

### One old code to several new codes

| Old code | Old name | New codes | New names | Year |
| --- | --- | --- | --- | --- |
| E10000021 | Northamptonshire | E06000061, E06000062 | North Northamptonshire, West Northamptonshire | 2021 |
| E10000006 | Cumbria | E06000063, E06000064 | Cumberland, Westmorland and Furness | 2023 |

Where a county split, the county's figure is carried to each successor for the
years before the split. That is an approximation, not a measurement, because the
two successors will not have resembled the county equally.

### Resolving collisions

Recoding creates two kinds of collision and they need opposite treatment, which
`geography.collapse` handles.

A merge is where several predecessors became one council. Bournemouth and Poole
both became Bournemouth, Christchurch and Poole, so both contribute a row for the
years before 2019. Counts are added and rates are averaged, weighted by workforce
size where a size is available, so the larger council counts for more.

A split is where one predecessor became several. A figure carried from the
predecessor is only useful in years where the successor reported nothing itself.
Where the successor did report, the carried figure is dropped, because a real
measurement always beats an inherited one. Before this rule was added, North
Northamptonshire had two rows for 2021, one carried from Northamptonshire and one
of its own.

## Regions

The Department for Education workforce file carries a region for every council
and splits London into an inner and an outer part. Those two are combined into
the single London region used by the Office for National Statistics.

Four councils are missing from that file. North Northamptonshire and West
Northamptonshire are missing because they were created partway through the
period. Kingston upon Thames and Richmond upon Thames are missing because they
run children's services through a shared arrangement and are reported under one
code. Their region is filled in from the Ofsted inspection file.

Ofsted publishes eight inspection regions rather than nine statistical regions,
because it runs the North East together with Yorkshire and the Humber. The
fallback mapping in `src/loaders.py` covers only the seven unambiguous regions,
and none of the four councils it fills sits in the combined region, so no council
is placed in the wrong statistical region.

## Client level data

### Coverage of the panel

The specification asked for a panel of quarters back to April 2024. Three
quarterly releases are published and their monthly windows overlap:

| Release | Months covered |
| --- | --- |
| To September 2025 | October 2024 to September 2025 |
| To December 2025 | January 2025 to December 2025 |
| To March 2026 | April 2025 to March 2026 |

Stitched together they give 18 monthly snapshots from October 2024 to March 2026.
Earlier releases are not available. The gov.uk collection "Monthly statistics for
adult social care, England" was checked and does not carry long-term support
tables; it covers provider occupancy, visiting, workforce and vaccination.

Where a month appears in more than one release, the value from the most recent
release is used, because later releases carry the publisher's corrections. The
September and December 2025 files used here are the corrected July 2026 versions.

### Suppression

The Department of Health and Social Care marks suppressed cells `[c]`. Those
become missing values, never zeros. A suppressed count is unknown, not absent,
and treating it as zero would pull an authority's rate down and could make it
look like an outlier.

### Table layout

Both the long-term support and the assessment tables put their column headings on
the third row, with two title rows above. Monthly columns are headed with a date
such as `31 March 2026 [p]` for long-term support and a month such as
`March 2026 [p]` for assessments. The `[p]` marker means provisional. The loader
strips it before parsing and reads an assessment month as the last day of that
month. Assessment tables also carry a `Total [p]` column, which the loader drops
so callers can sum whichever months they want.

## ASCOF

Responsibility for the Adult Social Care Outcomes Framework moved from NHS
England to the Department of Health and Social Care for 2024/25. The NHS England
Digital publication has no 2024/25 release, and its "current" page still resolves
to 2018/19. The 2024/25 data is on gov.uk and that is what is downloaded.

Measure 1A sits on sheet `Table_1a` with headings on row six. The loader keeps
rows where the demographic and the group are both `Total`, which is the headline
figure for each council.

Two councils have measure 1A suppressed, Derby and the Isles of Scilly, because
their survey response was too small to publish. They come through as missing.

## Skills for Care

The workforce estimates page named in the specification returns a 404. The
current data downloads page was found by browsing the site and the local area
file is downloaded from there.

The file publishes the vacancy rate as a proportion, so 0.062 means 6.2 per cent.
The loader multiplies by 100 so that every rate in this repository is on the same
percentage scale.

The sheet has one row for every combination of sector, service and job role. The
loader keeps the whole-area total, meaning all sectors, all services and all job
roles.

Three councils have no vacancy rate: the Isles of Scilly, Cumberland, and
Westmorland and Furness. Skills for Care has not yet split its Cumbria figures
between the two successor councils. Those councils drop out of the adult model
and stay in the funnel plots.

The workbook carries Microsoft information protection labels that openpyxl does
not recognise and warns about. The warning says nothing about the data and is
silenced in `src/loaders.py`.

## Department for Education releases

The children's social work workforce publication is not exposed through the
Explore Education Statistics API, so all three DfE sources are downloaded as
release zips through the content API. A loader finds the CSV it needs by the end
of the member name rather than the full path, because the publisher changes the
folder layout between releases more often than it changes file names. A missing
member raises an error that lists what the zip actually contains.

The children looked after file holds two measures of placement instability. The
one used here is `With 3 or more placements during the year`, matched exactly,
not the two year measure that also contains the words "3 or more".

## Ofsted

The release named in the specification does not exist under that name. The data
comes from "Local authority inspection outcomes as at 31 March 2026", whose
`ILACS_inspection_history` sheet carries every inspection from 2018 onwards with
its date, type and overall effectiveness grade.

Grades are converted to a rank where a bigger number is a worse judgement:
Outstanding 1, Good 2, Requires improvement to be good 3, Inadequate 4. Both
"Requires improvement" and "Requires improvement to be good" map to 3, because
the wording changed during the period and the judgement did not. A downgrade is
therefore any move to a higher rank.

## Denominators

The mid-2024 population estimates are used for every year of both projects. For
the adult project that means the March 2026 support counts sit over a mid-2024
denominator, so councils growing quickly look as though they support a slightly
higher share of adults than they do. For the children's project the same single
year of child population is applied across 2017 to 2025. Both are recorded as
limits in the project READMEs.
