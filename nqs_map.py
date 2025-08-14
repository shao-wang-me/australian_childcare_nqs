#!/usr/bin/env python3
# -*- coding: utf-8 -*-

_ICON_COLOURS = {
    'lightred',
    'black',
    'purple',
    'orange',
    'white',
    'lightgreen',
    'lightgray',
    'darkblue',
    'pink',
    'darkpurple',
    'lightblue',
    'green',
    'darkgreen',
    'darkred',
    'beige',
    'cadetblue',
    'gray',
    'blue',
    'red'
}

import argparse
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from datetime import datetime

def parse_args():
    p = argparse.ArgumentParser(description='Plot ACECQA / NQS services onto an interactive map.')
    p.add_argument('--csv', required=True, help='Path to the CSV file (the dataset you downloaded).')
    p.add_argument('--out', default='nqs_map.html', help='Output HTML map path (default: nqs_map.html).')
    p.add_argument('--zoom', type=int, default=11, help='Initial zoom level (default: 11).')
    return p.parse_args()

# 简单的日期解析（CSV 里常见格式如 23/06/2021 或 1/01/2012）
def parse_date(s: str) -> str:
    if pd.isna(s) or not str(s).strip():
        return ''
    txt = str(s).strip()
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try:
            return datetime.strptime(txt, fmt).date().isoformat()
        except Exception:
            continue
    # 兜底：直接返回原文
    return txt

def build_full_address(row) -> str:
    parts = []
    for key in ['Address Line 1', 'Address Line 2']:
        v = row.get(key, '')
        if pd.notna(v) and str(v).strip():
            parts.append(str(v).strip())
    # Suburb/Town, State, Postcode
    suburb = str(row.get('Suburb/Town', '') or '').strip()
    state = str(row.get('Address State', '') or '').strip()
    postcode = str(row.get('Postcode', '') or '').strip()
    tail = ' '.join([p for p in [suburb, state, postcode] if p])
    if tail:
        parts.append(tail)
    return ', '.join(parts)

def norm_rating(s: str) -> str:
    if not isinstance(s, str):
        return 'Not Rated'
    t = s.strip()
    if not t:
        return 'Not Rated'
    return t

# 为不同 Overall Rating 指定颜色（folium.Icon 支持的颜色名）
RATING_COLOR = {
    'Excellent': 'darkgreen',
    'Exceeding NQS': 'green',
    'Meeting NQS': 'blue',
    'Working Towards NQS': 'orange',
    'Significant Improvement Required': 'red',
    'Not Rated': 'gray'
}

# Quality Areas 显示名（中文说明可按需调整）
QA_LABELS = {
    'Quality Area 1': 'QA1 教育计划与实践',
    'Quality Area 2': 'QA2 儿童健康与安全',
    'Quality Area 3': 'QA3 物理环境',
    'Quality Area 4': 'QA4 人员安排',
    'Quality Area 5': 'QA5 与儿童关系',
    'Quality Area 6': 'QA6 与家庭和社区协作',
    'Quality Area 7': 'QA7 治理与领导',
}

def main():
    args = parse_args()
    df = pd.read_csv(args.csv)

    # 只保留有经纬度的记录
    if not {'Latitude', 'Longitude'}.issubset(df.columns):
        raise SystemExit('CSV 缺少 Latitude/Longitude 列。')

    df = df.copy()
    # 去两端空白
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()

    # 计算 Provider 名下的服务数量（满足“这个 provider 还有几家？”的需求）
    if 'Provider Name' in df.columns:
        provider_counts = df['Provider Name'].value_counts()
        df['Provider Service Count'] = df['Provider Name'].map(provider_counts)
    else:
        df['Provider Service Count'] = ''

    # 组合完整地址
    df['Full Address'] = df.apply(build_full_address, axis=1)

    # 解析评级日期
    if 'Final Report Sent Date' in df.columns:
        df['Final Report (ISO)'] = df['Final Report Sent Date'].apply(parse_date)
    else:
        df['Final Report (ISO)'] = ''

    # 规范 Overall Rating 并分配颜色
    df['Overall Rating (norm)'] = df['Overall Rating'].apply(norm_rating)
    df['Marker Color'] = df['Overall Rating (norm)'].map(RATING_COLOR).fillna('gray')

    # 地图中心：使用有效点的均值
    ok = df[['Latitude', 'Longitude']].dropna()
    if ok.empty:
        raise SystemExit('没有有效的经纬度可用于绘图。')
    center_lat, center_lng = ok['Latitude'].astype(float).mean(), ok['Longitude'].astype(float).mean()

    m = folium.Map(location=[center_lat, center_lng], zoom_start=args.zoom, control_scale=True)
    cluster = MarkerCluster(name='All services', show=True)
    cluster.add_to(m)

    # 构建气泡内容
    qa_cols = [c for c in QA_LABELS.keys() if c in df.columns]

    for _, row in df.iterrows():
        try:
            lat = float(row['Latitude'])
            lng = float(row['Longitude'])
        except Exception:
            continue

        service_name = row.get('Service Name', '')
        provider_name = row.get('Provider Name', '')
        provider_mgmt = row.get('Provider Management Type', '')
        provider_cnt = row.get('Provider Service Count', '')
        service_type = row.get('Service Type', '')
        service_sub_type = row.get('Service Sub Type', '')
        rating_overall = row.get('Overall Rating (norm)', '')
        rating_date = row.get('Final Report (ISO)', '')
        phone = row.get('Service phone number', '')
        addr = row.get('Full Address', '')
        approval_no = row.get('Service Approval Number', '')
        seifa = row.get('SEIFA', '')
        aria = row.get('ARIA+', '')
        max_places = row.get('Maximum total places', '')

        # 质量领域表格
        qa_rows = []
        for qc in qa_cols:
            val = row.get(qc, '')
            lab = QA_LABELS.get(qc, qc)
            qa_rows.append(f'<tr><td style="padding:2px 6px;white-space:nowrap;">{lab}</td>'
                           f'<td style="padding:2px 6px;">{val}</td></tr>')
        qa_table = ''
        if qa_rows:
            qa_table = f"""
            <div style="margin-top:6px;">
              <b>Quality Areas</b>
              <table style="font-size:12px;border-collapse:collapse;">{''.join(qa_rows)}</table>
            </div>
            """

        html = f"""
        <div style="min-width:300px;max-width:420px;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;">
          <div style="margin-bottom:6px;">
            <div style="font-size:16px;font-weight:600;line-height:1.2;">{service_name}</div>
            <div style="font-size:12px;color:#555;">Approval: {approval_no}</div>
          </div>

          <div style="font-size:13px;line-height:1.35;">
            <b>整体评级</b>：{rating_overall}<br>
            <b>评级时间</b>：{rating_date or '—'}<br>
            <b>服务类型</b>：{service_type or '—'}{(' / ' + service_sub_type) if service_sub_type else ''}<br>
            <b>Provider</b>：{provider_name or '—'}{f'（旗下服务数：{provider_cnt}）' if provider_cnt else ''}<br>
            <b>Provider Management Type</b>：{provider_mgmt or '—'}<br>
            <b>电话</b>：{phone or '—'}<br>
            <b>地址</b>：{addr or '—'}<br>
            <b>名额（Maximum total places）</b>：{max_places or '—'}<br>
            <b>SEIFA</b>：{seifa or '—'}；<b>ARIA+</b>：{aria or '—'}
          </div>

          {qa_table}
        </div>
        """

        popup = folium.Popup(html, max_width=450)
        icon = folium.Icon(color=row['Marker Color'], icon='info-sign')
        folium.Marker(
            location=[lat, lng],
            popup=popup,
            tooltip=service_name,
            icon=icon
        ).add_to(cluster)

    # 视野适配所有点
    m.fit_bounds([[ok['Latitude'].min(), ok['Longitude'].min()],
                  [ok['Latitude'].max(), ok['Longitude'].max()]])

    # 简单图例（右下角）
    legend_html = """
    <div style="
      position: fixed; bottom: 18px; right: 18px; z-index: 9999;
      background: white; padding: 8px 10px; border: 1px solid #ccc; border-radius: 6px;
      font-size: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.15);
    ">
      <div style="font-weight:600;margin-bottom:4px;">Overall Rating</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#2E8B57;border:1px solid #1e5a3a;margin-right:6px;"></span>Exceeding NQS</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#3388ff;border:1px solid #1d5fbf;margin-right:6px;"></span>Meeting NQS</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#f39c12;border:1px solid #b06e00;margin-right:6px;"></span>Working Towards NQS</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#d9534f;border:1px solid #922b21;margin-right:6px;"></span>Significant Improvement Required</div>
      <div><span style="display:inline-block;width:10px;height:10px;background:#9e9e9e;border:1px solid #616161;margin-right:6px;"></span>Not Rated / Unknown</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=True).add_to(m)
    m.save(args.out)
    print(f'✅ Done. Open: {args.out}')

if __name__ == '__main__':
    main()
