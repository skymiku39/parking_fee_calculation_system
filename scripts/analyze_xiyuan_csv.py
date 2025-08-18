import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List


def parse_money(val: str) -> Optional[int]:
    if val is None:
        return None
    s = str(val)
    s = s.replace(',', '').replace(' ', '').replace('"', '').strip()
    if s == '':
        return None
    # 有些行可能是 '1,000' 或 ' 1,000 '
    try:
        return int(s)
    except ValueError:
        # fallback: 去除非數字
        digits = ''.join(ch for ch in s if ch.isdigit())
        return int(digits) if digits else None


def parse_dt(val: str) -> Optional[datetime]:
    if not val:
        return None
    s = val.strip()
    # 例: 7/1/2024 13:11
    fmts = [
        '%m/%d/%Y %H:%M',
        '%m/%d/%Y %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d %H:%M:%S',
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def find_plan_id_by_name_substring(name_substring: str) -> Optional[str]:
    path = Path('config/user_defined_plans.json')
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    for pid, p in data.get('plans', {}).items():
        if name_substring in (p.get('name') or ''):
            return pid
    return None


def load_plan_caps(plan_id: str) -> Dict[str, Any]:
    path = Path('config/user_defined_plans.json')
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    p = data.get('plans', {}).get(plan_id) or {}
    return {
        'global_grace_time': p.get('global_grace_time', 0),
        'global_caps': p.get('global_caps', {}),
        'segment_type': p.get('segment_type'),
        'holiday_type': p.get('holiday_type'),
    }


def guess_reason(diff: int, enter: datetime, exit: datetime, result: Dict[str, Any], plan_meta: Dict[str, Any]) -> str:
    total_minutes = int((exit - enter).total_seconds() // 60)
    caps = plan_meta.get('global_caps') or {}
    cap_amount = caps.get('daily_cap_amount') if caps.get('daily_cap_enabled') else None
    if cap_amount is not None and result.get('total_amount') == cap_amount:
        return '可能觸發日封頂'
    if total_minutes <= (plan_meta.get('global_grace_time') or 0):
        return '可能因全域免費時間（短停）'
    if enter.date() != exit.date():
        return '跨日計費切割差異'
    # 假日/週末判定差異（簡單提示）
    if enter.weekday() >= 5 or exit.weekday() >= 5:
        return '週末/假日判定差異'
    # 小差距可能是向上取整與單位不一致
    if abs(diff) <= 10:
        return '取整/單位時間差異'
    return '費率/矩陣設定差異'


def build_inline_plan() -> Dict[str, Any]:
    # 萬華西園規則：平日30、假日40、無封頂、夜間 22:00-08:00
    # 假設單位60分鐘、向上取整、全域免費0
    segments = [
        {"name": "日間", "start": "08:00", "end": "22:00"},
        {"name": "夜間", "start": "22:00", "end": "08:00"},  # 跨日
    ]
    rate_matrix = {
        # 平日/假日：日間每30分，夜間每60分
        "日間_平日": {"unit_time": 30, "simple_rate": 30, "progressive_enabled": False, "grace_time": 0},
        "日間_假日": {"unit_time": 30, "simple_rate": 40, "progressive_enabled": False, "grace_time": 0},
        "夜間_平日": {"unit_time": 60, "simple_rate": 10, "progressive_enabled": False, "grace_time": 0},
        "夜間_假日": {"unit_time": 60, "simple_rate": 10, "progressive_enabled": False, "grace_time": 0},
    }
    return {
        "name": "萬華西園_校正",
        "segment_type": "任意段",
        "holiday_type": "平日假日",
        "segments": segments,
        "rate_matrix": rate_matrix,
        "global_caps": {"daily_cap_enabled": False},
        "global_grace_time": 0,
    }


def calc_end_pivot_units(ps, enter: datetime, exit: datetime, plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    以30分鐘為單位，對每個單位使用「單位結束時刻」所屬的時段/日期類別決定費率。
    """
    unit_minutes = 30
    total_minutes = int((exit - enter).total_seconds() // 60)
    if total_minutes <= 0:
        return {"success": True, "total_amount": 0, "session_details": [], "calculation_engine": "user_defined_billing_cycle"}

    # 切成30分鐘單位（最後不足一單位仍以一單位計）
    num_units = -(-total_minutes // unit_minutes)
    cursor = enter
    segments = plan.get('segments', [])
    rate_matrix = plan.get('rate_matrix', {})
    holiday_type = plan.get('holiday_type', '平日假日')

    def date_cat(dt: datetime) -> str:
        return ps.determine_date_category(dt, holiday_type)

    fee_total = 0
    details: List[Dict[str, Any]] = []

    for _ in range(num_units):
        period_start = cursor
        period_end = min(cursor + timedelta(minutes=unit_minutes), exit)

        # 決定費率的時間點改為單位結束時刻（靠近 period_end 的前一分鐘）
        pivot = period_end - timedelta(seconds=1)
        # 找到該時刻所在的時段
        seg = ps.find_active_segment_at_time(pivot, segments)
        if not seg:
            # 若未匹配任何時段，費用計0
            unit_fee = 0
            rate_desc = '無費率'
            unit = unit_minutes
        else:
            dc = date_cat(pivot)
            key = f"{seg['name']}_{dc}"
            cfg = rate_matrix.get(key, {})
            unit = cfg.get('unit_time', unit_minutes)
            rate = cfg.get('simple_rate', 0)
            # 向上取整（以30分鐘為一計，不足亦收一單位）
            units = 1
            unit_fee = rate
            rate_desc = f"{rate}元/{unit}分"

        fee_total += unit_fee
        details.append({
            'time_range': f"{period_start.strftime('%H:%M')}-{period_end.strftime('%H:%M')}",
            'duration': (period_end - period_start).seconds // 60,
            'label': seg['name'] if seg else '未匹配',
            'unit': unit,
            'rate': rate if seg else 0,
            'fee': unit_fee,
        })

        cursor = period_end
        if cursor >= exit:
            break

    return {
        'success': True,
        'calculation_engine': 'user_defined_billing_cycle',
        'total_amount': int(fee_total),
        'original_amount': int(fee_total),
        'manual_adjustment': 0,
        'session_details': details,
        'calculation_summary': f"30分單位(以結束時刻判斷) 共{num_units}單位",
        'enter_time': enter,
        'exit_time': exit,
        'total_duration_minutes': total_minutes,
    }


def main(csv_path: str, plan_keyword: str = '萬華西園', use_inline: bool = True) -> None:
    try:
        import sys, os
        sys.path.insert(0, os.getcwd())
        from app import parking_system  # 使用現行系統的計算流程
    except Exception as e:
        print(f'[ERROR] 載入系統失敗: {e}')
        return

    plan_id = None
    plan_inline: Optional[Dict[str, Any]] = None
    if use_inline:
        plan_inline = build_inline_plan()
        plan_meta = load_plan_caps(find_plan_id_by_name_substring(plan_keyword) or '')
    else:
        plan_id = find_plan_id_by_name_substring(plan_keyword)
        if not plan_id:
            print(f'[ERROR] 找不到包含「{plan_keyword}」的用戶自訂方案')
            return
        plan_meta = load_plan_caps(plan_id)

    rows = []
    p = Path(csv_path)
    if not p.exists():
        print(f'[ERROR] 檔案不存在: {p}')
        return

    with p.open('r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for idx, r in enumerate(reader, start=2):
            if not r or len(r) < 4:
                continue
            amt_raw, plate, enter_str, exit_str = r[0], r[1], r[2], r[3]
            expected = parse_money(amt_raw)
            enter_dt = parse_dt(enter_str)
            exit_dt = parse_dt(exit_str)
            if expected is None or not enter_dt or not exit_dt:
                rows.append({'line': idx, 'valid': False, 'reason': '格式錯誤', 'plate': plate})
                continue
            if enter_dt >= exit_dt:
                rows.append({'line': idx, 'valid': False, 'reason': '時間區間不合法', 'plate': plate})
                continue
            rows.append({
                'line': idx,
                'valid': True,
                'plate': plate,
                'expected': expected,
                'enter': enter_dt,
                'exit': exit_dt,
            })

    total = sum(1 for r in rows if r.get('valid'))
    if total == 0:
        print('[INFO] 無有效資料列可供比對')
        return

    matched = 0
    mismatches = []
    invalids = [r for r in rows if not r.get('valid')]

    for r in rows:
        if not r.get('valid'):
            continue
        if plan_inline is not None:
            # 以收費週期開始時刻判定（符合「計費時間前的時間為基準」）
            res = parking_system.calculate_fee_by_billing_cycles(
                enter_time=r['enter'],
                exit_time=r['exit'],
                plan_data=plan_inline,
            )
        else:
            res = parking_system.calculate_parking_fee(
                enter_time=r['enter'],
                exit_time=r['exit'],
                plan_id=plan_id,
            )
        computed = int(res.get('total_amount') or 0)
        diff = computed - int(r['expected'])
        r['computed'] = computed
        r['diff'] = diff
        r['engine'] = res.get('calculation_engine')
        if diff == 0:
            matched += 1
        else:
            reason = guess_reason(diff, r['enter'], r['exit'], res, plan_meta)
            # 蒐集系統實際計算明細
            detail_entry = {
                'line': r['line'],
                'plate': r['plate'],
                'enter': r['enter'],
                'exit': r['exit'],
                'expected': r['expected'],
                'computed': computed,
                'diff': diff,
                'engine': res.get('calculation_engine'),
                'reason': reason,
                'total_duration_minutes': int((r['exit'] - r['enter']).total_seconds() // 60),
                'calculation_summary': res.get('calculation_summary'),
                'session_details': res.get('session_details', []),
            }
            mismatches.append(detail_entry)

    accuracy = matched / total * 100.0

    print(f'方案: {plan_keyword} ({"inline" if use_inline else "ID="+plan_id})')
    print(f'有效資料列: {total}，正確: {matched} ({accuracy:.2f}%)，錯誤: {len(mismatches)}，格式/時間錯誤: {len(invalids)}')

    if invalids:
        print('\n[無效資料列 範例最多5筆]')
        for r in invalids[:5]:
            print(f"  行{r['line']}: {r.get('reason')} 車號={r.get('plate')}")

    if mismatches:
        print('\n[不一致資料 範例最多20筆]')
        for r in mismatches[:20]:
            dur_min = r.get('total_duration_minutes')
            print(
                f"  行{r['line']} 車號={r['plate']} 期望={r['expected']} 計算={r['computed']} 差額={r['diff']} 分鐘={dur_min} 理由={r.get('reason','')}"
            )

        # 匯出完整差異明細
        out_dir = Path('log')
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv = out_dir / 'xiyuan_mismatch_report.csv'
        with out_csv.open('w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['line', 'plate', 'enter', 'exit', 'expected', 'computed', 'diff', 'duration_minutes', 'reason'])
            for r in mismatches:
                dur_min = r.get('total_duration_minutes')
                w.writerow([
                    r['line'], r['plate'], r['enter'].strftime('%Y-%m-%d %H:%M'), r['exit'].strftime('%Y-%m-%d %H:%M'),
                    r['expected'], r['computed'], r['diff'], dur_min, r.get('reason','')
                ])
        # JSON 細節檔
        out_json = out_dir / 'xiyuan_mismatch_details.json'
        serializable = []
        for r in mismatches:
            serializable.append({
                'line': r['line'],
                'plate': r['plate'],
                'enter': r['enter'].strftime('%Y-%m-%d %H:%M'),
                'exit': r['exit'].strftime('%Y-%m-%d %H:%M'),
                'expected': r['expected'],
                'computed': r['computed'],
                'diff': r['diff'],
                'engine': r.get('engine'),
                'reason': r.get('reason'),
                'total_duration_minutes': r.get('total_duration_minutes'),
                'calculation_summary': r.get('calculation_summary'),
                'session_details': r.get('session_details'),
            })
        out_json.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\n[已輸出差異報表] {out_csv.as_posix()}\n[已輸出差異細節] {out_json.as_posix()}")

    # 分類統計
    reason_count: Dict[str, int] = {}
    for r in mismatches:
        key = r.get('reason') or '其他'
        reason_count[key] = reason_count.get(key, 0) + 1

    if reason_count:
        print('\n[可能原因統計]')
        for k, v in sorted(reason_count.items(), key=lambda x: -x[1]):
            print(f'  {k}: {v}')


if __name__ == '__main__':
    # 預設讀取專案根目錄的「西園出入時間金額明細.csv」，使用 inline 校正方案
    main('西園出入時間金額明細.csv', plan_keyword='萬華西園', use_inline=True)


