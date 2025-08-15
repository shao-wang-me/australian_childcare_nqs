#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import html
import pandas as pd
import folium
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
    'Quality Area 2': 'QA2 Children’s health and safety',
    'Quality Area 3': 'QA3 Physical environment',
    'Quality Area 4': 'QA4 Staffing arrangements',
    'Quality Area 5': 'QA5 Relationships with children',
    'Quality Area 6': 'QA6 Collaborative partnerships',
    'Quality Area 7': 'QA7 Governance and leadership',
}

def parse_args():
    p = argparse.ArgumentParser(
        description='Make an interactive NQS map with layered toggles and filtering.'
    )
    p.add_argument('--csv', required=True, help='Path to the CSV (National Registers with NQS).')
    p.add_argument('--out', default='nqs_map.html', help='Output HTML file.')
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

def main():
    args = parse_args()

    # --- Read CSV as strings to avoid dtype warnings; disable low-memory chunking ---
    read_kwargs = dict(
        dtype='string',
        low_memory=False,
        na_filter=False,   # keep "Met"/"Not Met" as strings
        encoding='utf-8'
    )
    if args.engine == 'pyarrow':
        read_kwargs['engine'] = 'pyarrow'
    df = pd.read_csv(args.csv, **read_kwargs)
    df.columns = [c.strip() for c in df.columns]

    # Required columns
    need_cols = {'Latitude', 'Longitude', 'Service Name', 'Overall Rating'}
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        raise SystemExit(f'Missing required columns: {missing}')

    # Optional filter
    if args.filter.strip():
        try:
            df = df.query(args.filter, engine='python')
        except Exception as e:
            raise SystemExit(f'Invalid --filter expression: {e}')

    # Export filtered set if requested
    if args.export_filtered:
        df.to_csv(args.export_filtered, index=False)

    # Prepare typed columns and derived fields
    lat = pd.to_numeric(df['Latitude'], errors='coerce')
    lng = pd.to_numeric(df['Longitude'], errors='coerce')

    # Parse Final Report date -> ISO string
    if 'Final Report Sent Date' in df.columns:
        rating_date_iso = pd.to_datetime(
            df['Final Report Sent Date'].astype('string').str.strip(),
            dayfirst=True, errors='coerce'
        ).dt.date.astype('string')
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

    # Base map
    center = [df2['_lat'].mean(), df2['_lng'].mean()]
    tile = folium.TileLayer("OpenStreetMap", overlay=True, control=False)
    tile._id = 'openstreetmap'
    m = folium.Map(tiles=tile, location=center, zoom_start=args.zoom, control_scale=True, prefer_canvas=True)
    m._id = 'cc_nqs_map'

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
        # id = f'{r.get('Provider ID', '')}_{r.get('Service Approval Number', '')}_{r.get('Service Name', '')}_{float(r['_lat'])}_{float(r['_lng'])}'
        id = f'{r.get('Provider ID', '')}_{r.get('Service Approval Number', '')}'
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
            <b>Rating date</b>: {rating_date or '—'}<br>
            <b>Service type</b>: {service_type or '—'}{(' / ' + service_sub_type) if service_sub_type else ''}<br>
            <b>Provider</b>: {provider_name or '—'}{f' (services: {provider_cnt})' if provider_cnt else ''}<br>
            <b>Provider management type</b>: {provider_mgmt or '—'}<br>
            <b>Phone</b>: {phone or '—'}<br>
            <b>Address</b>: {addr or '—'}<br>
            <b>Maximum total places</b>: {max_places or '—'}<br>
            <b>SEIFA</b>: {seifa or '—'}; <b>ARIA+</b>: {aria or '—'}
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

    # Fit bounds
    bb = df2[['_lat','_lng']].agg(['min','max'])
    m.fit_bounds([[bb.loc['min','_lat'], bb.loc['min','_lng']],
                  [bb.loc['max','_lat'], bb.loc['max','_lng']]])

    # Legend: rating colors + note on clusters
    legend_html = """
    <div style="
      position: fixed; bottom: 18px; right: 18px; z-index: 9999;
      background: white; padding: 10px 12px; border: 1px solid #ccc; border-radius: 8px;
      font-size: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.15); max-width: 260px;
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
    </div>
    """
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

    locate_me = folium.plugins.LocateControl(auto_start=False).add_to(m)
    locate_me._id = 'locate_me'

    control = folium.LayerControl(collapsed=False).add_to(m)
    control._id = 'control'
    m.save(args.out)
    print(f'✅ Done. Open: {args.out}')

if __name__ == '__main__':
    main()
