#!/usr/bin/env python3
"""Build current and historical service datasets from ACECQA exports."""

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registers', type=Path, required=True)
    parser.add_argument('--nqs-timeseries', type=Path, required=True)
    parser.add_argument('--out-current', type=Path, required=True)
    parser.add_argument('--out-history', type=Path, required=True)
    parser.add_argument('--latest-sheet', default='Q22026data')
    return parser.parse_args()


def clean_key(series: pd.Series) -> pd.Series:
    return series.astype('string').str.strip().str.upper()


def choose_register_value(merged: pd.DataFrame, name: str, fallback: str | None = None) -> pd.Series:
    register_name = f'{name}_registers'
    nqs_name = f'{name}_nqs'
    if register_name in merged and nqs_name in merged:
        register_values = merged[register_name].astype('string').str.strip()
        return register_values.where(register_values.ne(''), merged[nqs_name])
    if register_name in merged:
        return merged[register_name]
    if name in merged:
        return merged[name]
    if fallback and fallback in merged:
        return merged[fallback]
    return merged.get(nqs_name, pd.Series('', index=merged.index, dtype='string'))


def load_latest_nqs(path: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, dtype='string')
    df.columns = [str(column).strip() for column in df.columns]
    if 'Service Approval Number' not in df:
        raise SystemExit(f'{sheet} is missing Service Approval Number')
    df['_service_key'] = clean_key(df['Service Approval Number'])
    return df.drop_duplicates('_service_key', keep='last')


def load_registers(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype='string', na_filter=False)
    df.columns = [str(column).strip() for column in df.columns]
    df = df.rename(columns={
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
    })
    if 'ServiceApprovalNumber' not in df:
        if 'Service Approval Number' not in df:
            raise SystemExit('National Registers file is missing ServiceApprovalNumber')
    df['_service_key'] = clean_key(df['Service Approval Number'])
    return df.drop_duplicates('_service_key', keep='last')


def build_current(registers: pd.DataFrame, nqs: pd.DataFrame) -> pd.DataFrame:
    merged = nqs.merge(registers, on='_service_key', how='outer', suffixes=('_nqs', '_registers'))

    output = pd.DataFrame(index=merged.index)
    output['Service Approval Number'] = choose_register_value(merged, 'Service Approval Number', 'ServiceApprovalNumber')
    output['Service Name'] = choose_register_value(merged, 'Service Name', 'ServiceName')
    output['Provider ID'] = choose_register_value(merged, 'Provider ID', 'Provider Approval Number')
    output['Provider Name'] = choose_register_value(merged, 'Provider Name', 'ProviderLegalName')
    output['Provider Management Type'] = choose_register_value(merged, 'Provider Management Type')
    output['Service Type'] = choose_register_value(merged, 'Service Type')
    output['Address Line 1'] = choose_register_value(merged, 'Address Line 1', 'ServiceAddress')
    output['Suburb/Town'] = choose_register_value(merged, 'Suburb/Town', 'Suburb')
    output['Address State'] = choose_register_value(merged, 'Address State', 'State')
    output['Postcode'] = choose_register_value(merged, 'Postcode')
    output['Service phone number'] = choose_register_value(merged, 'Service phone number', 'Phone')
    output['Maximum total places'] = choose_register_value(merged, 'Maximum total places', 'NumberOfApprovedPlaces')
    output['Overall Rating'] = choose_register_value(merged, 'Overall Rating', 'OverallRating')
    output['Final Report Sent Date'] = choose_register_value(merged, 'Final Report Sent Date', 'RatingsIssued')
    output['Temporarily Closed'] = choose_register_value(merged, 'Temporarily Closed')
    for number in range(1, 8):
        output[f'Quality Area {number}'] = choose_register_value(merged, f'Quality Area {number}', f'QualityArea{number}Rating')
    output['Latitude'] = pd.to_numeric(choose_register_value(merged, 'Latitude'), errors='coerce')
    output['Longitude'] = pd.to_numeric(choose_register_value(merged, 'Longitude'), errors='coerce')

    output = output[output['Service Approval Number'].astype('string').str.strip().ne('')]
    output = output.drop_duplicates('Service Approval Number', keep='last')
    return output


def build_history(path: Path) -> pd.DataFrame:
    frames = []
    for sheet in pd.ExcelFile(path).sheet_names:
        if not sheet.startswith('Q') or not sheet.endswith('data'):
            continue
        frame = pd.read_excel(path, sheet_name=sheet, dtype='string')
        frame.columns = [str(column).strip() for column in frame.columns]
        id_column = 'Service Approval Number' if 'Service Approval Number' in frame else 'Service ID'
        required = {id_column, 'Overall Rating', 'Final Report Sent Date'}
        if not required <= set(frame.columns):
            continue
        frames.append(frame[[id_column, 'Overall Rating', 'Final Report Sent Date']].assign(quarter=sheet[:5]))

    if not frames:
        raise SystemExit('No quarterly NQS sheets found in time series workbook')
    history = pd.concat(frames, ignore_index=True)
    history = history.rename(columns={history.columns[0]: 'Service Approval Number'})
    history['Service Approval Number'] = clean_key(history['Service Approval Number'])
    return history.drop_duplicates(['Service Approval Number', 'quarter'], keep='last')


def main() -> None:
    args = parse_args()
    args.out_current.parent.mkdir(parents=True, exist_ok=True)
    args.out_history.parent.mkdir(parents=True, exist_ok=True)

    registers = load_registers(args.registers)
    nqs = load_latest_nqs(args.nqs_timeseries, args.latest_sheet)
    current = build_current(registers, nqs)
    history = build_history(args.nqs_timeseries)

    current.to_csv(args.out_current, index=False)
    history.to_csv(args.out_history, index=False)
    print(f'current services: {len(current):,}')
    print(f'history rows: {len(history):,}')
    print(f'current output: {args.out_current}')
    print(f'history output: {args.out_history}')


if __name__ == '__main__':
    main()
