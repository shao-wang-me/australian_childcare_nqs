# Similar Sites and Product References

Last reviewed: 2026-09-05

This is a living reference for Australian childcare search, NQS rating and
service-map products. Add new findings here when a new comparable product,
data source or useful interaction pattern is discovered.

## Official references

### StartingBlocks.gov.au

- URL: https://www.startingblocks.gov.au/find-child-care
- Owner: ACECQA
- Positioning: family-facing national service finder
- Useful patterns: distance search, map view, service type, age, session type,
  rating, vacancies, inclusions, compare and shortlist
- Product lesson: this is the benchmark for the complete parent decision flow;
  the project should learn from it without trying to reproduce every feature

### ACECQA National Registers

- URL: https://www.acecqa.gov.au/resources/national-registers
- Owner: ACECQA / NQA IT System
- Positioning: official current register of approved services and providers
- Useful patterns: service and provider search, approval numbers, state and
  service-type filters, current operational information
- Product lesson: use this as the current service master rather than treating a
  quarterly NQS workbook as the only source of truth

### ACECQA NQF Snapshots

- URL: https://www.acecqa.gov.au/resources/snapshot-and-reports/nqf-snapshots
- Owner: ACECQA
- Positioning: quarterly NQS data and sector analysis
- Useful patterns: rating distribution, historical quarterly comparisons and
  clear data-as-at dates
- Product lesson: keep current rating and historical rating as separate data
  concepts

## Independent references

### AussieDataGal Childcare Quality Rating Map

- URL: https://aussiedatagal.github.io/childcare-quality-ratings/
- Discovery: Reddit post in r/BabyBumpsandBeyondAu
- Positioning: lightweight public NQS rating visualisation
- Useful patterns: simple map-first exploration and readable rating legend
- Limitation: the author described the data refresh as manual at the time of
  the Reddit discussion

### ChildcareCheck

- URL: https://childcarecheck.com.au/
- Owner: SecaRoo
- Useful patterns: search by suburb, postcode or centre; Cards/Table/Map views;
  data freshness and approximate-location disclosure
- Product lesson: make location accuracy and data freshness visible

### SuburbCheck Childcare Map

- URL: https://www.suburbcheck.com.au/childcare-map
- Useful patterns: rating distribution, service-type filtering, NQS explainer
  and practical FAQ content
- Product lesson: explain ratings before asking users to interpret them

### ChildcareScout

- URL: https://www.childcarescout.au/childcare
- Useful patterns: near-me search, map view, state, rating, service type,
  nature of care, operating status, sorting and compare actions
- Product lesson: the list workflow matters as much as the map

## Current direction for this project

The project is a transparent NQS data map rather than a full replacement for
StartingBlocks. Prioritise:

1. Current service data from National Registers
2. Latest rating from quarterly NQS data
3. Rating history from the NQS time-series workbook
4. Map, list and filter views that share one result set
5. Explicit handling of missing addresses, missing ratings and approximate
   locations

Review this document when a new comparable site or official data source is
found. Do not copy private, sponsored or user-generated data without checking
its provenance and terms.
