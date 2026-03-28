#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import html
from pathlib import Path
from time import perf_counter
from typing import Tuple
import pandas as pd
import folium
from branca.element import Element, MacroElement, Template
from folium.plugins import MarkerCluster, FastMarkerCluster, FeatureGroupSubGroup

# Color map for ratings, including the top "Excellent"
RATING_COLOR = {
    'Excellent': 'darkpurple',              # Highest tier
    'Exceeding NQS': 'green',
    'Meeting NQS': 'blue',
    'Working Towards NQS': 'orange',
    'Significant Improvement Required': 'red',
    'Not Rated': 'gray'
}

# Quality Area labels (English)
QA_LABELS = {
    'Quality Area 1': 'QA1 Educational program and practice',
    'Quality Area 2': "QA2 Children's health and safety",
    'Quality Area 3': 'QA3 Physical environment',
    'Quality Area 4': 'QA4 Staffing arrangements',
    'Quality Area 5': 'QA5 Relationships with children',
    'Quality Area 6': 'QA6 Collaborative partnerships',
    'Quality Area 7': 'QA7 Governance and leadership',
}

OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
)
CARTO_TILES = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
CARTO_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors '
    '&copy; <a href="https://carto.com/attributions">CARTO</a>'
)
DEFAULT_SHEET_CANDIDATES = (
    'Approved Services',
    'Q42025data',
    'Q32025data',
    'Q22025data',
    'Q12025data',
)


class TileFallbackControl(MacroElement):
    """Choose tiles client-side: local files use CARTO, hosted pages prefer OSM."""

    def __init__(self, map_name: str, osm_layer_name: str, carto_layer_name: str):
        super().__init__()
        self._name = 'TileFallbackControl'
        self.map_name = map_name
        self.osm_layer_name = osm_layer_name
        self.carto_layer_name = carto_layer_name
        self._template = Template(
            """
            {% macro script(this, kwargs) %}
            (function() {
                var map = {{ this.map_name }};
                var osm = {{ this.osm_layer_name }};
                var carto = {{ this.carto_layer_name }};
                var preferOsmTiles = window.location.protocol !== "file:";
                var osmTileErrorCount = 0;
                var osmTileLoadedSuccessfully = false;
                var switchedToCartoFallback = false;

                function switchToCartoFallback() {
                    if (switchedToCartoFallback) {
                        return;
                    }

                    switchedToCartoFallback = true;
                    if (map.hasLayer(osm)) {
                        map.removeLayer(osm);
                    }
                    if (!map.hasLayer(carto)) {
                        carto.addTo(map);
                    }
                    console.warn("OpenStreetMap tiles unavailable; switched to CARTO fallback.");
                }

                if (map.hasLayer(carto) && preferOsmTiles) {
                    map.removeLayer(carto);
                }
                if (preferOsmTiles && !map.hasLayer(osm)) {
                    osm.addTo(map);
                }
                if (!preferOsmTiles && !map.hasLayer(carto)) {
                    carto.addTo(map);
                }

                osm.on("tileerror", function() {
                    osmTileErrorCount += 1;
                    if (!osmTileLoadedSuccessfully || osmTileErrorCount >= 3) {
                        switchToCartoFallback();
                    }
                });

                osm.on("tileload", function() {
                    osmTileLoadedSuccessfully = true;
                });

                osm.on("load", function() {
                    osmTileErrorCount = 0;
                });

                if (preferOsmTiles) {
                    window.setTimeout(function() {
                        if (!osmTileLoadedSuccessfully) {
                            switchToCartoFallback();
                        }
                    }, 4000);
                }
            })();
            {% endmacro %}
            """
        )


def normalize_site_url(site_url: str) -> str:
    site_url = (site_url or '').strip()
    if not site_url:
        return ''
    return site_url.rstrip('/') + '/'

def parse_args():
    p = argparse.ArgumentParser(
        description='Make an interactive NQS map with layered toggles and filtering.'
    )
    p.add_argument('--input', dest='input_path', default='',
                   help='Path to the source data file (.csv, .xlsx, .xls).')
    p.add_argument('--csv', dest='csv_path', default='',
                   help='Backward-compatible alias for --input.')
    p.add_argument('--sheet', default='',
                   help='Worksheet name for Excel inputs. If omitted, the script auto-detects one.')
    p.add_argument('--out', default='docs/index.html', help='Output HTML file.')
    p.add_argument('--zoom', type=int, default=10, help='Initial zoom level.')
    p.add_argument('--engine', choices=['c', 'pyarrow'], default='c',
                   help='pandas read_csv engine. pyarrow is faster if installed.')
    p.add_argument('--fast-cluster', action='store_true',
                   help='Use FastMarkerCluster (very fast, but no rich HTML popups).')
    p.add_argument('--facets', default='',
                   help='Choose ONE facet to create layers for: state | rating | type. '
                        'Example: --facets rating')
    p.add_argument('--filter', default='',
                   help='Optional pandas query filter. Use backticks for column names with spaces.')
    p.add_argument('--export-filtered', default='',
                   help='If set, export the filtered DataFrame to this CSV path.')
    p.add_argument('--export-normalized', default='',
                   help='If set, export the normalized input table to this CSV path before filtering.')
    p.add_argument('--site-url', default='',
                   help='Canonical public URL for the built page, e.g. https://user.github.io/project/.')
    p.add_argument('--site-title', default='Australian Childcare NQS Map',
                   help='HTML title and OG title for the generated page.')
    p.add_argument('--site-description', default='Interactive map of Australian childcare services using quarterly ACECQA NQS data.',
                   help='Meta description and OG description for the generated page.')
    p.add_argument('--build-rev', default='',
                   help='Optional build revision label, such as the current git commit.')
    return p.parse_args()

def build_full_address_cols(df: pd.DataFrame) -> pd.Series:
    """Vectorised address concatenation."""
    a1 = df.get('Address Line 1', '').fillna('').astype('string').str.strip()
    a2 = df.get('Address Line 2', '').fillna('').astype('string').str.strip()
    suburb = df.get('Suburb/Town', '').fillna('').astype('string').str.strip()
    state = df.get('Address State', '').fillna('').astype('string').str.strip()
    postcode = df.get('Postcode', '').fillna('').astype('string').str.strip()

    tail = (suburb + ' ' + state + ' ' + postcode).str.replace(r'\s+', ' ', regex=True).str.strip()
    stacked = pd.concat([a1.replace('', pd.NA),
                         a2.replace('', pd.NA),
                         tail.replace('', pd.NA)], axis=1)
    return stacked.apply(lambda r: ', '.join(r.dropna().astype(str)), axis=1).fillna('')

import re

# JavaScript reserved words (ES2015+, simplified list)
JS_RESERVED_WORDS = {
    "break", "case", "catch", "class", "const", "continue",
    "debugger", "default", "delete", "do", "else", "export", "extends",
    "finally", "for", "function", "if", "import", "in", "instanceof",
    "new", "return", "super", "switch", "this", "throw", "try", "typeof",
    "var", "void", "while", "with", "yield", "enum", "await", "implements",
    "package", "protected", "static", "interface", "private", "public",
    "null", "true", "false"
}

def to_js_identifier(s: str) -> str:
    """Convert a string into a valid JavaScript identifier (ASCII-only)."""
    if not s:
        return "_"

    # Replace invalid characters with underscores
    s = re.sub(r"[^a-zA-Z0-9_$]", "_", s)

    # Ensure the first character is valid
    if not re.match(r"[a-zA-Z_$]", s[0]):
        s = "_" + s

    # Avoid reserved words
    if s in JS_RESERVED_WORDS:
        s += "_"

    return s


def resolve_input_path(args) -> Path:
    input_path = (args.input_path or args.csv_path or '').strip()
    if not input_path:
        raise SystemExit('Provide an input file with --input (or legacy --csv).')
    path = Path(input_path)
    if not path.exists():
        raise SystemExit(f'Input file not found: {path}')
    return path


def read_csv_input(path: Path, engine: str) -> pd.DataFrame:
    read_kwargs = dict(
        dtype='string',
        low_memory=False,
        na_filter=False,
        encoding='utf-8'
    )
    if engine == 'pyarrow':
        read_kwargs['engine'] = 'pyarrow'
    return pd.read_csv(path, **read_kwargs)


def choose_excel_sheet(path: Path, requested_sheet: str) -> str:
    sheet_names = pd.ExcelFile(path).sheet_names
    if requested_sheet:
        if requested_sheet not in sheet_names:
            raise SystemExit(f'Sheet not found in {path.name}: {requested_sheet}')
        return requested_sheet

    for candidate in DEFAULT_SHEET_CANDIDATES:
        if candidate in sheet_names:
            return candidate

    lowered = {name.lower(): name for name in sheet_names}
    for candidate in ('approved services', 'q42025data', 'q32025data', 'q22025data', 'q12025data'):
        if candidate in lowered:
            return lowered[candidate]

    raise SystemExit(
        'Could not auto-detect a usable Excel sheet. '
        f'Available sheets: {", ".join(sheet_names)}'
    )


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        'ServiceApprovalNumber': 'Service Approval Number',
        'ServiceName': 'Service Name',
        'Provider Approval Number': 'Provider ID',
        'ProviderLegalName': 'Provider Name',
        'ServiceType': 'Service Type',
        'ServiceAddress': 'Address Line 1',
        'Suburb': 'Suburb/Town',
        'State': 'Address State',
        'Phone': 'Service phone number',
        'NumberOfApprovedPlaces': 'Maximum total places',
        'QualityArea1Rating': 'Quality Area 1',
        'QualityArea2Rating': 'Quality Area 2',
        'QualityArea3Rating': 'Quality Area 3',
        'QualityArea4Rating': 'Quality Area 4',
        'QualityArea5Rating': 'Quality Area 5',
        'QualityArea6Rating': 'Quality Area 6',
        'QualityArea7Rating': 'Quality Area 7',
        'OverallRating': 'Overall Rating',
        'RatingsIssued': 'Final Report Sent Date',
    }
    df = df.rename(columns=rename_map)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_input_dataframe(path: Path, engine: str, requested_sheet: str) -> Tuple[pd.DataFrame, str]:
    suffix = path.suffix.lower()
    if suffix == '.csv':
        df = read_csv_input(path, engine=engine)
        source_label = path.name
    elif suffix in {'.xlsx', '.xls'}:
        sheet_name = choose_excel_sheet(path, requested_sheet=requested_sheet)
        df = pd.read_excel(path, sheet_name=sheet_name, dtype='string')
        source_label = f'{path.name} [{sheet_name}]'
    else:
        raise SystemExit(f'Unsupported input type: {path.suffix}')

    df = normalize_column_names(df)
    return df, source_label


def add_seo_metadata(map_obj, site_title: str, site_description: str, site_url: str) -> None:
    header = map_obj.get_root().header
    title_text = html.escape(site_title)
    description_text = html.escape(site_description)

    header.add_child(Element(f'<title>{title_text}</title>'))
    header.add_child(Element(f'<meta name="description" content="{description_text}">'))
    header.add_child(Element(f'<meta property="og:title" content="{title_text}">'))
    header.add_child(Element(f'<meta property="og:description" content="{description_text}">'))
    header.add_child(Element('<meta property="og:type" content="website">'))
    header.add_child(Element('<meta name="twitter:card" content="summary">'))

    if site_url:
        site_url_text = html.escape(site_url, quote=True)
        header.add_child(Element(f'<link rel="canonical" href="{site_url_text}">'))
        header.add_child(Element(f'<meta property="og:url" content="{site_url_text}">'))

def main():
    t0 = perf_counter()
    t_last = t0

    def log_stage(label: str) -> None:
        nonlocal t_last
        now = perf_counter()
        print(f'[{label}] {now - t_last:.2f}s')
        t_last = now

    args = parse_args()
    input_path = resolve_input_path(args)
    df, source_label = load_input_dataframe(input_path, engine=args.engine, requested_sheet=args.sheet)
    site_url = normalize_site_url(args.site_url)
    log_stage('load input')

    if args.export_normalized:
        df.to_csv(args.export_normalized, index=False)
        log_stage('export normalized')

    # Required columns
    need_cols = {'Latitude', 'Longitude', 'Service Name', 'Overall Rating'}
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        raise SystemExit(
            f'Missing required columns in {source_label}: {missing}. '
            'For maps, use an NQS dataset/sheet that includes coordinates.'
        )

    # Optional filter
    if args.filter.strip():
        try:
            df = df.query(args.filter, engine='python')
        except Exception as e:
            raise SystemExit(f'Invalid --filter expression: {e}')
        log_stage('apply filter')

    # Export filtered set if requested
    if args.export_filtered:
        df.to_csv(args.export_filtered, index=False)

    # Prepare typed columns and derived fields
    lat = pd.to_numeric(df['Latitude'], errors='coerce')
    lng = pd.to_numeric(df['Longitude'], errors='coerce')

    # Parse Final Report date -> ISO string.
    # Quarterly CSV exports tend to use day/month/year, while Excel-derived files may
    # already be ISO-like timestamps. Parse both without emitting format warnings.
    if 'Final Report Sent Date' in df.columns:
        report_dates = df['Final Report Sent Date'].astype('string').str.strip()
        rating_date = pd.to_datetime(
            report_dates,
            format='%d/%m/%Y',
            errors='coerce'
        )
        missing_dates = rating_date.isna()
        if missing_dates.any():
            rating_date.loc[missing_dates] = pd.to_datetime(
                report_dates.loc[missing_dates],
                errors='coerce'
            )
        rating_date_iso = rating_date.dt.date.astype('string')
    else:
        rating_date_iso = pd.Series([''] * len(df), dtype='string')

    # Provider service count
    if 'Provider Name' in df.columns:
        provider_counts = df['Provider Name'].value_counts()
        provider_service_count = df['Provider Name'].map(provider_counts).astype('Int64').astype('string')
    else:
        provider_service_count = pd.Series([''] * len(df), dtype='string')

    # Address
    full_address = build_full_address_cols(df)

    # Normalise overall rating (map empty to "Not Rated")
    overall = df['Overall Rating'].fillna('').str.strip()
    overall = overall.where(overall.ne(''), 'Not Rated')
    marker_color = overall.map(RATING_COLOR).fillna('gray')

    # Keep only valid coords
    df2 = df.assign(
        _lat=lat, _lng=lng,
        _overall=overall,
        _marker_color=marker_color,
        _full_address=full_address,
        _rating_date_iso=rating_date_iso,
        _provider_service_count=provider_service_count
    )
    df2 = df2[df2['_lat'].notna() & df2['_lng'].notna()]
    if df2.empty:
        raise SystemExit('No valid coordinates to plot.')
    log_stage('prepare dataframe')

    # Base map. Start with CARTO active; client-side logic can switch to OSM when appropriate.
    center = [df2['_lat'].mean(), df2['_lng'].mean()]
    m = folium.Map(
        tiles=None,
        location=center,
        zoom_start=args.zoom,
        control_scale=True,
        prefer_canvas=True,
    )
    m._id = 'cc_nqs_map'
    add_seo_metadata(m, args.site_title, args.site_description, site_url)
    carto_tile = folium.TileLayer(
        tiles=CARTO_TILES,
        attr=CARTO_ATTRIBUTION,
        name='CARTO Light',
        overlay=False,
        control=True,
        show=True,
        subdomains='abcd',
        detect_retina=True,
        max_native_zoom=19,
        max_zoom=19,
    ).add_to(m)
    carto_tile._id = 'carto_light'
    osm_tile = folium.TileLayer(
        tiles=OSM_TILES,
        attr=OSM_ATTRIBUTION,
        name='OpenStreetMap',
        overlay=False,
        control=True,
        show=False,
        max_native_zoom=19,
        max_zoom=19,
    ).add_to(m)
    osm_tile._id = 'openstreetmap'
    log_stage('init map')

    # Decide on ONE facet (for performance)
    facets = [f.strip().lower() for f in args.facets.split(',') if f.strip()]
    valid_facet_keys = {'state', 'rating', 'type'}
    facets = [f for f in facets if f in valid_facet_keys]
    facet = facets[0] if facets else ''

    # Helper to escape HTML
    def esc(x): return html.escape(str(x)) if pd.notna(x) else ''

    # Quality area columns existing in data
    qa_cols = [c for c in QA_LABELS.keys() if c in df2.columns]

    # Get ID for a row
    def get_row_id(r) -> str:
        # Keep ids stable and compact so popup bindings remain predictable in generated JS.
        id = f"{r.get('Provider ID', '')}_{r.get('Service Approval Number', '')}"
        id = to_js_identifier(id)
        return id

    # Build popup HTML for a row
    def build_popup(r) -> str:
        service_name = esc(r.get('Service Name', ''))
        provider_id = esc(r.get('Provider ID', ''))
        provider_name = esc(r.get('Provider Name', ''))
        provider_mgmt = esc(r.get('Provider Management Type', ''))
        provider_cnt = esc(r.get('_provider_service_count', ''))
        service_type = esc(r.get('Service Type', ''))
        service_sub_type = esc(r.get('Service Sub Type', ''))
        rating_overall = esc(r.get('_overall', 'Not Rated'))
        rating_date = esc(r.get('_rating_date_iso', ''))
        phone = esc(r.get('Service phone number', ''))
        addr = esc(r.get('_full_address', ''))
        approval_no = esc(r.get('Service Approval Number', ''))
        seifa = esc(r.get('SEIFA', ''))
        aria = esc(r.get('ARIA+', ''))
        max_places = esc(r.get('Maximum total places', ''))

        qa_rows = []
        for qc in qa_cols:
            lab = html.escape(QA_LABELS.get(qc, qc))
            val = esc(r.get(qc, ''))
            qa_rows.append(
                f'<tr><td style="padding:2px 6px;white-space:nowrap;">{lab}</td>'
                f'<td style="padding:2px 6px;">{val}</td></tr>'
            )
        qa_table = ''
        if qa_rows:
            qa_table = (
                '<div style="margin-top:6px;">'
                '<b>Quality Areas</b>'
                '<table style="font-size:12px;border-collapse:collapse;">'
                + ''.join(qa_rows) + '</table></div>'
            )

        popup_html_content = folium.Element(f"""
        <div style="min-width:300px;max-width:440px;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;">
          <div style="margin-bottom:6px;">
            <div style="font-size:16px;font-weight:600;line-height:1.2;">{service_name}</div>
            <div style="font-size:12px;color:#555;">Approval: {approval_no}</div>
            <div style="font-size:12px;color:#555;">Provider: {provider_id}</div>
          </div>

          <div style="font-size:13px;line-height:1.35;">
            <b>Overall rating</b>: {rating_overall}<br>
            <b>Rating date</b>: {rating_date or '-'}<br>
            <b>Service type</b>: {service_type or '-'}{(' / ' + service_sub_type) if service_sub_type else ''}<br>
            <b>Provider</b>: {provider_name or '-'}{f' (services: {provider_cnt})' if provider_cnt else ''}<br>
            <b>Provider management type</b>: {provider_mgmt or '-'}<br>
            <b>Phone</b>: {phone or '-'}<br>
            <b>Address</b>: {addr or '-'}<br>
            <b>Maximum total places</b>: {max_places or '-'}<br>
            <b>SEIFA</b>: {seifa or '-'}; <b>ARIA+</b>: {aria or '-'}
          </div>

          {qa_table}
        </div>
        """)
        popup_html_content._id = f'popup_html_content_{get_row_id(r)}'
        return popup_html_content

    # Base cluster to host subgroups (keeps clustering consistent)
    marker_cluster = FastMarkerCluster if args.fast_cluster else MarkerCluster
    base_cluster = MarkerCluster(
        name='All services',
        control=False,
        options=dict(
            showCoverageOnHover=True,
            spiderfyOnMaxZoom=True,
            disableClusteringAtZoom=14
        ),
    ).add_to(m)
    base_cluster._id = 'base_cluster'

    def add_rows_to_group(group, rows):
        for _, r in rows.iterrows():
            id = get_row_id(r)
            popup = folium.Popup(build_popup(r), max_width=480, lazy=True)
            popup._id = id
            popup.html._id = f'popup_html_{id}'
            icon = folium.Icon(color=str(r['_marker_color']), icon='info-sign')
            icon._id = id
            marker = folium.Marker(
                location=[float(r['_lat']), float(r['_lng'])],
                popup=popup,
                tooltip=esc(r.get('Service Name', '')),
                icon=icon,
                lazy=True
            ).add_to(group)
            marker._id = id

    if not facet:
        # No facets: dump everything into the base cluster
        add_rows_to_group(base_cluster, df2)
    else:
        # Build exactly ONE facet dimension for performance
        if facet == 'state':
            for state_val, rows in df2.groupby('Address State', dropna=False):
                subgroup = FeatureGroupSubGroup(base_cluster, name=f"State: {state_val or 'Unknown'}")
                subgroup._id = to_js_identifier(state_val or 'Unknown')
                m.add_child(subgroup)  # must attach subgroups to the map to be toggleable
                add_rows_to_group(subgroup, rows)

        elif facet == 'rating':
            order = ['Excellent', 'Exceeding NQS', 'Meeting NQS',
                     'Working Towards NQS', 'Significant Improvement Required', 'Not Rated']
            for rating_val in order:
                rows = df2[df2['_overall'] == rating_val]
                if rows.empty:
                    continue
                subgroup = FeatureGroupSubGroup(base_cluster, name=f"Rating: {rating_val}")
                subgroup._id = to_js_identifier(rating_val)
                m.add_child(subgroup)
                add_rows_to_group(subgroup, rows)

        elif facet == 'type':
            for type_val, rows in df2.groupby('Service Type', dropna=False):
                subgroup = FeatureGroupSubGroup(base_cluster, name=f"Type: {type_val or 'Unknown'}")
                subgroup._id = to_js_identifier(type_val or 'Unknown')
                m.add_child(subgroup)
                add_rows_to_group(subgroup, rows)
    log_stage('build markers')

    # Fit bounds
    bb = df2[['_lat','_lng']].agg(['min','max'])
    m.fit_bounds([[bb.loc['min','_lat'], bb.loc['min','_lng']],
                  [bb.loc['max','_lat'], bb.loc['max','_lng']]])
    log_stage('fit bounds')

    latest_rating_date = ''
    earliest_rating_date = ''
    if '_rating_date_iso' in df2.columns:
        valid_rating_dates = df2['_rating_date_iso'].dropna()
        valid_rating_dates = valid_rating_dates[valid_rating_dates.ne('')]
        if not valid_rating_dates.empty:
            earliest_rating_date = str(valid_rating_dates.min())
            latest_rating_date = str(valid_rating_dates.max())

    # Legend + data source summary
    record_count = f"{len(df2):,}"
    build_rev_text = html.escape(args.build_rev or 'Unknown')
    data_label = html.escape(input_path.stem.replace('NQS Data ', 'ACECQA ').replace('.XLSX', '').replace('.CSV', ''))

    legend_html = """
    <div style="
      position: fixed; bottom: 18px; right: 18px; z-index: 9999;
      background: white; padding: 10px 12px; border: 1px solid #ccc; border-radius: 8px;
      font-size: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.15); max-width: 310px;
    ">
      <div style="font-weight:700;margin-bottom:6px;">Marker colors by Overall Rating</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#6f42c1;border:1px solid #4d2f8a;margin-right:6px;"></span>Excellent</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#2E8B57;border:1px solid #1e5a3a;margin-right:6px;"></span>Exceeding NQS</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#3388ff;border:1px solid #1d5fbf;margin-right:6px;"></span>Meeting NQS</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#f39c12;border:1px solid #b06e00;margin-right:6px;"></span>Working Towards NQS</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#d9534f;border:1px solid #922b21;margin-right:6px;"></span>Significant Improvement Required</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#9e9e9e;border:1px solid #616161;margin-right:6px;"></span>Not Rated / Unknown</div>
      <hr style="margin:6px 0;border:none;border-top:1px solid #eee;">
      <div style="font-size:11px;color:#555;">
        Cluster bubbles use the default count-based style (not rating colors).
      </div>
      <hr style="margin:6px 0;border:none;border-top:1px solid #eee;">
      <div style="font-weight:700;margin-bottom:4px;">Data source</div>
      <div style="font-size:11px;line-height:1.45;color:#333;">
        <div><b>Source</b>: DATA_LABEL</div>
        <div><b>Services</b>: RECORD_COUNT</div>
        <div><b>Rev</b>: BUILD_REV</div>
      </div>
    </div>
    """
    legend_html = (legend_html
        .replace('DATA_LABEL', data_label)
        .replace('RECORD_COUNT', record_count)
        .replace('BUILD_REV', build_rev_text)
    )
    legend = folium.Element(legend_html)
    legend._id = 'legend'
    m.get_root().html.add_child(legend)

    fullscreen = folium.plugins.Fullscreen(
        position="topright",
        title="Expand me",
        title_cancel="Exit me",
        force_separate_button=True,
    ).add_to(m)
    fullscreen._id = 'fullscreen'

    address_search = folium.plugins.Geocoder().add_to(m)
    address_search._id = 'address_search'

    locate_me = folium.plugins.LocateControl(
        auto_start=False,
        keepCurrentZoomLevel=True
    ).add_to(m)
    locate_me._id = 'locate_me'

    tile_fallback = TileFallbackControl(m.get_name(), osm_tile.get_name(), carto_tile.get_name())
    m.add_child(tile_fallback)

    control = folium.LayerControl(collapsed=False).add_to(m)
    control._id = 'control'
    log_stage('finalize controls')

    m.save(args.out)
    log_stage('save html')
    print(f'Done. Open: {args.out}')
    print(f'[total] {perf_counter() - t0:.2f}s')

if __name__ == '__main__':
    main()
