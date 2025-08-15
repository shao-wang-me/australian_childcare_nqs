## Usage

```shell
# Most useful
python nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map.html --facets rating --fast-cluster

# Basic
python nqs_map_v3.py --csv "NQS Data Q2 2025.CSV" --out nqs_map.html

# Faster CSV reading (if pyarrow installed)
python nqs_map_v3.py --csv "NQS Data Q2 2025.CSV" --out nqs_map.html --engine pyarrow

# Add layered toggles by state + rating + type
python nqs_map_v3.py --csv "NQS Data Q2 2025.CSV" --out nqs_map.html --facets state,rating,type

# Filter then export a filtered CSV and map only those records
python nqs_map_v3.py --csv "NQS Data Q2 2025.CSV" --out nqs_map_vic_exceeding.html \
  --filter "`Address State`=='VIC' and `Overall Rating` in ['Exceeding NQS','Excellent']" \
  --export-filtered filtered_vic_exceeding.csv

# When too many points: use fast cluster (no rich popups, best for overview)
python nqs_map_v3.py --csv "NQS Data Q2 2025.CSV" --out nqs_map_fast.html --fast-cluster
```

> Notes on --filter:
> 
> Pandas query supports backticks around column names with spaces.
> Examples:
> 
> ```
> `Address State`=='VIC' and `Overall Rating`=='Excellent'`
> `Service Type`.str.contains('Centre-Based', case=False)
> ```

## TODO

1. cluster style customisation
2. provider id
3. explain NQS etc. (link to A...)
4. legends not shown in fullscreen
5. starting blocks links
6. red if report date is too long ago
7. tel:
8. google maps link?