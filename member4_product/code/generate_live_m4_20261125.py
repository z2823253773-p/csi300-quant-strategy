# -*- coding: utf-8 -*-
"""
独立增量实盘信号生成器（2026-11-25）
- 历史基座：严格读取组员 1 冻结的 Tushare 双股票池数据（截至 2026-10-30），绝不修改原库。
- 11 月增量行情（2026-11-02 ~ 2026-11-25）：通过腾讯公开复权日线 + 批量快照接口拉取。
- 因子清洗与合成：100% 复刻组员 2 原版 M4 公式（BP/EP 截面去极值标准化；LowVol60/LowTurn20 申万行业+对数流通市值中性化标准化；四因子等权）。
- 先在 2026-10-29 交叉校验与组员 2 官方 score_M4.parquet 的相关性（断言 > 0.9999），再输出 2026-11-25 沪深300调仓清单与中证500建仓清单。
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/henryz/Desktop/量化课程/大作业")
DATA_BASE = ROOT / "01_组员上游交付/组员1_数据/Tushare_双股票池完整数据与代码/tushare_data"
M2_BASE = ROOT / "01_组员上游交付/组员2_因子与信号"
OUT_DIR = ROOT / "02_组员4_工作区/member4/xueqiu"
CURR_HOLD_CSV = OUT_DIR / "最新持仓_前30只备用_2026-10-30.csv"

SIGNAL_DATE_TARGET = "2026-11-25"


def to_tx_code(ts_code: str) -> str:
    num, exch = ts_code.split(".")
    return f"{exch.lower()}{num}"


def fetch_tx_kline(ts_code: str) -> tuple[str, list[dict], str | None]:
    tx = to_tx_code(ts_code)
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tx},day,2026-10-25,2026-11-26,40,hfq"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                j = json.loads(resp.read().decode("utf-8", errors="ignore"))
            d = j.get("data", {}).get(tx, {})
            rows = d.get("hfqday") or d.get("day") or []
            out = []
            for r in rows:
                if len(r) >= 6:
                    out.append(
                        {
                            "trade_date": pd.Timestamp(r[0]),
                            "open_hfq": float(r[1]),
                            "close_hfq": float(r[2]),
                            "high_hfq": float(r[3]),
                            "low_hfq": float(r[4]),
                            "vol_lots": float(r[5]),
                        }
                    )
            return ts_code, out, None
        except Exception as exc:
            if attempt == 2:
                return ts_code, [], str(exc)
            time.sleep(0.4 * (attempt + 1))
    return ts_code, [], "unknown"


def fetch_tx_quotes(ts_codes: list[str]) -> pd.DataFrame:
    rows = []
    chunk_size = 50
    for i in range(0, len(ts_codes), chunk_size):
        chunk = ts_codes[i : i + chunk_size]
        tx_map = {to_tx_code(c): c for c in chunk}
        url = "https://qt.gtimg.cn/q=" + ",".join(tx_map.keys())
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    text = resp.read().decode("gbk", errors="ignore")
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        for line in text.strip().splitlines():
            if '="' not in line:
                continue
            prefix, body = line.split('="', 1)
            tx = prefix.replace("v_", "").strip()
            ts_code = tx_map.get(tx)
            if not ts_code:
                continue
            p = body.rstrip('";').split("~")
            if len(p) < 47:
                continue

            def fnum(idx: int) -> float:
                try:
                    v = float(p[idx])
                    return v if np.isfinite(v) else np.nan
                except Exception:
                    return np.nan

            name = p[1].strip()
            price = fnum(3)
            preclose = fnum(4)
            vol_lots = fnum(6)
            quote_time = p[30].strip() if len(p) > 30 else ""
            turn_pct = fnum(38)
            pe_ttm = fnum(39)
            float_mv_yi = fnum(44)
            total_mv_yi = fnum(45)
            pb = fnum(46)
            is_st = bool(re.match(r"^(?:\*?ST|S\*?ST)|退", name, re.IGNORECASE))
            rows.append(
                {
                    "stock_code": ts_code,
                    "stock_name": name,
                    "price": price,
                    "preclose": preclose,
                    "vol_lots_quote": vol_lots,
                    "quote_time": quote_time,
                    "turn_quote": turn_pct,
                    "pe_ttm": pe_ttm,
                    "pb": pb,
                    "float_mv_yi": float_mv_yi,
                    "total_mv_yi": total_mv_yi,
                    "is_st": is_st,
                }
            )
    return pd.DataFrame(rows).set_index("stock_code")


def clean_cross_section(
    raw: pd.Series,
    mask: pd.Series,
    sector: pd.Series,
    ln_size: pd.Series,
    neutral: bool = True,
) -> pd.Series:
    """严格复刻 member2 run_pool.py 的单截面 clean() + residual() + zscore()。"""
    v = raw.where(mask).replace([np.inf, -np.inf], np.nan).astype(float)
    med = v.median()
    mad_s = 1.4826 * (v - med).abs().median()
    if not (np.isfinite(mad_s) and mad_s > 1e-12):
        mad_s = (v.quantile(0.75) - v.quantile(0.25)) / 1.349
    if np.isfinite(mad_s) and mad_s > 0:
        v = v.clip(med - 5.0 * mad_s, med + 5.0 * mad_s)
    if not neutral:
        sd = v.std(ddof=1)
        if not (np.isfinite(sd) and sd > 1e-10):
            return pd.Series(np.nan, index=raw.index)
        return (v - v.mean()) / sd

    # Industry + log float mv residualization + z-score
    sec = sector.reindex(raw.index).fillna("未分类")
    sz = ln_size.reindex(raw.index).astype(float)
    ok = v.notna() & sz.notna() & np.isfinite(v) & np.isfinite(sz)
    out = pd.Series(np.nan, index=raw.index, dtype=float)
    if int(ok.sum()) < 30:
        return out
    g = pd.Categorical(sec[ok]).codes
    count = np.bincount(g).clip(1)
    vv = v[ok].to_numpy(dtype=float)
    a = vv - np.bincount(g, weights=vv)[g] / count[g]
    ss_vec = sz[ok].to_numpy(dtype=float)
    ss_vec = ss_vec - np.bincount(g, weights=ss_vec)[g] / count[g]
    ss = float(ss_vec @ ss_vec)
    if int(ok.sum()) <= len(np.unique(g)) + int(ss > 1e-12) + 10:
        return out
    if ss > 1e-12:
        a = a - ss_vec * (float(ss_vec @ a) / ss)
    sd = float(a.std(ddof=1))
    if sd < 1e-10:
        return out
    a = a / sd
    out.loc[ok] = a
    return out


def find_m2_score_path(pool: str) -> Path | None:
    candidates = [
        M2_BASE / "member2_v3/hs300_clean/signals/score_M4.parquet" if pool == "hs300" else M2_BASE / "member2_v3/zz500/signals/score_M4.parquet",
        M2_BASE / f"v3/{pool}/signals/score_M4.parquet",
    ]
    for p in candidates:
        if p.is_file():
            return p
    for p in M2_BASE.rglob("score_M4.parquet"):
        if pool in str(p) and ("clean" in str(p) or pool == "zz500"):
            return p
    return None


def process_pool(pool: str) -> tuple[pd.DataFrame, dict]:
    proc = DATA_BASE / pool / "processed"
    hc = pd.read_parquet(proc / "historical_constituents.parquet")
    last_eff = hc["eff_date"].max()
    const_codes = sorted(hc.loc[hc["eff_date"] == last_eff, "stock_code"].unique())

    close_hfq_hist = pd.read_parquet(proc / "matrix_close_hfq.parquet").sort_index()
    turn_hist = pd.read_parquet(proc / "matrix_turn.parquet").sort_index()
    bp_hist = pd.read_parquet(proc / "matrix_bp.parquet").sort_index()
    ep_hist = pd.read_parquet(proc / "matrix_ep.parquet").sort_index()
    mv_hist = pd.read_parquet(proc / "matrix_ln_float_mv_proxy.parquet").sort_index()
    mask_hist = pd.read_parquet(proc / "matrix_tradable_mask.parquet").sort_index().fillna(False).astype(bool)
    vol_hist = pd.read_parquet(proc / "matrix_volume.parquet").sort_index()

    panel = pd.read_parquet(
        proc / "clean_daily_panel.parquet",
        columns=["trade_date", "stock_code", "sw_l1_name", "is_suspended", "tradestatus"],
    )
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])
    last_panel = panel[panel["trade_date"] == panel["trade_date"].max()].set_index("stock_code")
    sw_map = (
        panel.dropna(subset=["sw_l1_name"])
        .sort_values("trade_date")
        .groupby("stock_code")["sw_l1_name"]
        .last()
        .reindex(const_codes)
        .fillna("未分类")
    )

    # 1. Self-validation on 2026-10-29 against Member 2's official score_M4.parquet
    val_date = pd.Timestamp("2026-10-29")
    ret_hist = close_hfq_hist.pct_change(fill_method=None)
    valid_hist = mask_hist & vol_hist.gt(0)
    turn_v = turn_hist.where(valid_hist)
    lv_1029 = -ret_hist.rolling(60, min_periods=40).std().loc[val_date]
    lt_1029 = -np.log(turn_v.rolling(20, min_periods=15).mean().where(lambda x: x > 0)).loc[val_date]
    sec_1029 = (
        panel[panel["trade_date"] == val_date]
        .set_index("stock_code")["sw_l1_name"]
        .reindex(close_hfq_hist.columns)
        .fillna("未分类")
    )
    m_1029 = valid_hist.loc[val_date]
    s_bp = clean_cross_section(bp_hist.loc[val_date], m_1029, sec_1029, mv_hist.loc[val_date], neutral=False)
    s_ep = clean_cross_section(ep_hist.loc[val_date], m_1029, sec_1029, mv_hist.loc[val_date], neutral=False)
    s_lv = clean_cross_section(lv_1029, m_1029, sec_1029, mv_hist.loc[val_date], neutral=True)
    s_lt = clean_cross_section(lt_1029, m_1029, sec_1029, mv_hist.loc[val_date], neutral=True)
    m4_1029_self = (s_bp + s_ep + s_lv + s_lt) / 4.0

    m2_path = find_m2_score_path(pool)
    val_corr = np.nan
    val_max_abs = np.nan
    if m2_path is not None:
        m2_m4 = pd.read_parquet(m2_path).loc[val_date].reindex(m4_1029_self.index)
        both = m4_1029_self.notna() & m2_m4.notna()
        val_corr = float(m4_1029_self[both].corr(m2_m4[both]))
        val_max_abs = float((m4_1029_self[both] - m2_m4[both]).abs().max())
        print(f"[{pool}] 2026-10-29 parity check vs M2 official: n={int(both.sum())}, corr={val_corr:.6f}, max_abs_diff={val_max_abs:.6f}")

    # 2. Fetch live quotes & Nov klines for all current constituents
    print(f"[{pool}] Fetching live Tencent quotes for {len(const_codes)} constituents...")
    quotes = fetch_tx_quotes(const_codes)
    print(f"[{pool}] Quotes fetched: {len(quotes)}/{len(const_codes)}")

    print(f"[{pool}] Fetching Nov daily hfq klines for {len(const_codes)} constituents...")
    t0 = time.time()
    kline_map = {}
    failures = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for code, rows, err in ex.map(fetch_tx_kline, const_codes):
            if err or not rows:
                failures.append((code, err))
            else:
                kline_map[code] = pd.DataFrame(rows).drop_duplicates("trade_date").set_index("trade_date").sort_index()
    print(f"[{pool}] Klines fetched: {len(kline_map)}/{len(const_codes)} in {time.time() - t0:.1f}s (failures={len(failures)})")

    # Determine Nov trading calendar (dates > 2026-10-30 up to 2026-11-25)
    all_nov_dates = sorted(
        {
            dt
            for df in kline_map.values()
            for dt in df.index
            if pd.Timestamp("2026-10-30") < dt <= pd.Timestamp(SIGNAL_DATE_TARGET)
        }
    )
    latest_dt = max(all_nov_dates)
    print(f"[{pool}] Nov trading days ({len(all_nov_dates)}): {all_nov_dates[0].date()} .. {latest_dt.date()}")

    # 3. Stitch returns and turnover cleanly onto last 80 historical days
    hist_tail_dates = close_hfq_hist.index[-80:]
    ret_tail = ret_hist.loc[hist_tail_dates, const_codes].copy()
    turn_tail = turn_v.loc[hist_tail_dates, const_codes].copy()

    nov_ret = pd.DataFrame(np.nan, index=all_nov_dates, columns=const_codes, dtype=float)
    nov_turn = pd.DataFrame(np.nan, index=all_nov_dates, columns=const_codes, dtype=float)

    for code in const_codes:
        kdf = kline_map.get(code)
        if kdf is None or kdf.empty:
            continue
        # Daily return from Tencent hfq close (includes 10-30 anchor so 11-02 has exact return)
        kret = kdf["close_hfq"].pct_change(fill_method=None)
        for dt in all_nov_dates:
            if dt in kret.index and kdf.loc[dt, "vol_lots"] > 0:
                nov_ret.loc[dt, code] = kret.loc[dt]

        # Calibrate turn_pct per lot using live quote (today's turn / today's vol) or float_shares
        q = quotes.loc[code] if code in quotes.index else None
        turn_per_lot = np.nan
        # First try overlap on 2026-10-30 between Tushare turn and Tencent vol_lots
        dt_1030 = pd.Timestamp("2026-10-30")
        if dt_1030 in kdf.index and kdf.loc[dt_1030, "vol_lots"] > 0 and pd.notna(turn_tail.loc[dt_1030, code]) and turn_tail.loc[dt_1030, code] > 0:
            turn_per_lot = float(turn_tail.loc[dt_1030, code]) / float(kdf.loc[dt_1030, "vol_lots"])
        elif q is not None and pd.notna(q["float_mv_yi"]) and q["float_mv_yi"] > 0 and pd.notna(q["price"]) and q["price"] > 0:
            float_shares = q["float_mv_yi"] * 1e8 / q["price"]
            turn_per_lot = (100.0 / float_shares) * 100.0

        if np.isfinite(turn_per_lot) and turn_per_lot > 0:
            for dt in all_nov_dates:
                if dt in kdf.index and kdf.loc[dt, "vol_lots"] > 0:
                    nov_turn.loc[dt, code] = float(kdf.loc[dt, "vol_lots"]) * turn_per_lot
        # Override latest date with exact quote turnover if traded today
        if q is not None and pd.notna(q["turn_quote"]) and q["turn_quote"] > 0 and latest_dt in nov_turn.index:
            nov_turn.loc[latest_dt, code] = float(q["turn_quote"])

    full_ret = pd.concat([ret_tail, nov_ret])
    full_turn = pd.concat([turn_tail, nov_turn])

    # 4. Compute raw M4 factors on latest_dt (2026-11-25)
    raw_lv60 = -full_ret.rolling(60, min_periods=40).std().loc[latest_dt]
    raw_lt20 = -np.log(full_turn.rolling(20, min_periods=15).mean().where(lambda x: x > 0)).loc[latest_dt]

    q_aligned = quotes.reindex(const_codes)
    raw_bp = 1.0 / q_aligned["pb"].where(q_aligned["pb"].gt(0))
    raw_ep = 1.0 / q_aligned["pe_ttm"].where(q_aligned["pe_ttm"].gt(0))
    ln_float_mv = np.log((q_aligned["float_mv_yi"] * 1e8).where(q_aligned["float_mv_yi"].gt(0)))
    # Fallback to 10-30 ln_float_mv if any quote missing float_mv
    ln_float_mv = ln_float_mv.fillna(mv_hist.loc[pd.Timestamp("2026-10-30")].reindex(const_codes))

    # Tradable & non-ST mask on latest_dt
    traded_today = pd.Series(
        [
            (c in kline_map and latest_dt in kline_map[c].index and kline_map[c].loc[latest_dt, "vol_lots"] > 0)
            for c in const_codes
        ],
        index=const_codes,
    )
    not_st = ~q_aligned["is_st"].fillna(False).astype(bool)
    mask_live = traded_today & not_st & q_aligned["price"].gt(0)

    z_bp = clean_cross_section(raw_bp, mask_live, sw_map, ln_float_mv, neutral=False)
    z_ep = clean_cross_section(raw_ep, mask_live, sw_map, ln_float_mv, neutral=False)
    z_lv = clean_cross_section(raw_lv60, mask_live, sw_map, ln_float_mv, neutral=True)
    z_lt = clean_cross_section(raw_lt20, mask_live, sw_map, ln_float_mv, neutral=True)

    m4_score = (z_bp + z_ep + z_lv + z_lt) / 4.0

    df_out = pd.DataFrame(
        {
            "stock_code": const_codes,
            "stock_name": q_aligned["stock_name"].values,
            "sw_l1_name": sw_map.values,
            "signal_date": latest_dt.strftime("%Y-%m-%d"),
            "price": q_aligned["price"].values,
            "pb": q_aligned["pb"].values,
            "pe_ttm": q_aligned["pe_ttm"].values,
            "float_mv_yi": q_aligned["float_mv_yi"].values,
            "turn_today": q_aligned["turn_quote"].values,
            "is_st": q_aligned["is_st"].fillna(False).values,
            "traded_today": traded_today.values,
            "z_bp": z_bp.values,
            "z_ep": z_ep.values,
            "z_lowvol_60": z_lv.values,
            "z_lowturn_20": z_lt.values,
            "m4_score": m4_score.values,
        }
    )
    eligible = df_out[df_out["m4_score"].notna()].copy()
    eligible = eligible.sort_values(["m4_score", "stock_code"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    eligible["m4_rank"] = np.arange(1, len(eligible) + 1)

    audit = {
        "pool": pool,
        "constituent_eff_date": str(last_eff)[:10],
        "n_constituents": len(const_codes),
        "n_quotes": int(len(quotes)),
        "n_klines": int(len(kline_map)),
        "kline_failures": len(failures),
        "signal_date": latest_dt.strftime("%Y-%m-%d"),
        "n_traded_non_st": int(mask_live.sum()),
        "n_scored_m4": int(len(eligible)),
        "parity_20261029_corr": round(val_corr, 6) if np.isfinite(val_corr) else None,
        "parity_20261029_max_abs_diff": round(val_max_abs, 6) if np.isfinite(val_max_abs) else None,
    }
    return eligible, audit


def select_xq30(eligible: pd.DataFrame, prev_codes: list[str] | None, buffer_k: int = 45) -> pd.DataFrame:
    ranked = eligible.sort_values(["m4_score", "stock_code"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    if prev_codes:
        prev_set = set(prev_codes)
        top_buf = ranked.head(buffer_k)
        kept = top_buf[top_buf["stock_code"].isin(prev_set)].copy()
        kept["select_reason"] = "前45名缓冲保留"
        need = 30 - len(kept)
        adds = ranked[~ranked["stock_code"].isin(set(kept["stock_code"]))].head(need).copy()
        adds["select_reason"] = "新入选补足30只"
        chosen = pd.concat([kept, adds], ignore_index=True)
    else:
        chosen = ranked.head(30).copy()
        chosen["select_reason"] = "首次建仓前30名"

    # Sort chosen 30 by M4 score descending (tie-break by stock_code ascending) -> Top 10 x 4%, Next 20 x 3%
    chosen = chosen.sort_values(["m4_score", "stock_code"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    chosen["portfolio_rank"] = np.arange(1, len(chosen) + 1)
    chosen["target_weight_pct"] = [4] * 10 + [3] * 20
    assert len(chosen) == 30 and int(chosen["target_weight_pct"].sum()) == 100
    return chosen


def main() -> None:
    hs_elig, hs_audit = process_pool("hs300")
    zz_elig, zz_audit = process_pool("zz500")

    # Current ZH3689205 holdings (built on 2026-11-18 from M0a Top 30: Top 10 x 4% + Next 20 x 3%)
    curr_df = pd.read_csv(CURR_HOLD_CSV)
    curr_codes = list(curr_df["股票代码"])
    curr_weights = {code: (4 if idx < 10 else 3) for idx, code in enumerate(curr_codes)}
    curr_names = dict(zip(curr_df["股票代码"], curr_df["股票名称"]))
    curr_ind = dict(zip(curr_df["股票代码"], curr_df["申万一级行业"]))

    hs_target = select_xq30(hs_elig, prev_codes=curr_codes, buffer_k=45)
    zz_target = select_xq30(zz_elig, prev_codes=None, buffer_k=45)

    # Save full target tables
    hs_target_path = OUT_DIR / "HS300_M4_2026-11-25_雪球30只目标持仓.csv"
    zz_target_path = OUT_DIR / "ZZ500_M4_2026-11-25_雪球30只首次建仓清单.csv"
    hs_target.to_csv(hs_target_path, index=False, encoding="utf-8-sig")
    zz_target.to_csv(zz_target_path, index=False, encoding="utf-8-sig")

    # Build explicit ZH3689205 rebalance action sheet
    hs_rank_map = hs_elig.set_index("stock_code")["m4_rank"].to_dict()
    hs_score_map = hs_elig.set_index("stock_code")["m4_score"].to_dict()
    hs_price_map = hs_elig.set_index("stock_code")["price"].to_dict()
    tgt_weights = dict(zip(hs_target["stock_code"], hs_target["target_weight_pct"]))
    tgt_names = dict(zip(hs_target["stock_code"], hs_target["stock_name"]))
    tgt_ind = dict(zip(hs_target["stock_code"], hs_target["sw_l1_name"]))
    tgt_reason = dict(zip(hs_target["stock_code"], hs_target["select_reason"]))

    all_codes = sorted(set(curr_weights) | set(tgt_weights))
    actions = []
    for c in all_codes:
        w0 = curr_weights.get(c, 0)
        w1 = tgt_weights.get(c, 0)
        dw = w1 - w0
        if w0 > 0 and w1 == 0:
            act = "1_清仓卖出"
        elif w0 > 0 and w1 > 0 and dw < 0:
            act = "2_减仓调权重"
        elif w0 > 0 and w1 > 0 and dw > 0:
            act = "3_加仓调权重"
        elif w0 == 0 and w1 > 0:
            act = "4_新买入"
        else:
            act = "5_持有不变"
        actions.append(
            {
                "操作类型": act,
                "股票代码": c,
                "股票名称": tgt_names.get(c, curr_names.get(c, "")),
                "申万一级行业": tgt_ind.get(c, curr_ind.get(c, "")),
                "原权重(%)": w0,
                "目标权重(%)": w1,
                "权重变动(%)": dw,
                "M4全池排名": hs_rank_map.get(c, np.nan),
                "M4综合得分": round(float(hs_score_map[c]), 4) if c in hs_score_map else np.nan,
                "最新收盘价(元)": hs_price_map.get(c, np.nan),
                "备注": tgt_reason.get(c, "跌出前45名缓冲区"),
            }
        )
    act_df = pd.DataFrame(actions).sort_values(["操作类型", "M4全池排名", "股票代码"]).reset_index(drop=True)
    act_path = OUT_DIR / "HS300_M4_2026-11-25_ZH3689205调仓操作清单.csv"
    act_df.to_csv(act_path, index=False, encoding="utf-8-sig")

    one_way_turn = float(act_df["权重变动(%)"].abs().sum() / 2.0)
    hs_audit["zh3689205_kept_count"] = int((act_df["原权重(%)"] > 0).astype(int).mul((act_df["目标权重(%)"] > 0).astype(int)).sum())
    hs_audit["zh3689205_sell_count"] = int((act_df["操作类型"] == "1_清仓卖出").sum())
    hs_audit["zh3689205_buy_count"] = int((act_df["操作类型"] == "4_新买入").sum())
    hs_audit["zh3689205_one_way_turnover_pct"] = round(one_way_turn, 2)
    hs_audit["hs300_top_industries"] = hs_target.groupby("sw_l1_name")["target_weight_pct"].sum().sort_values(ascending=False).to_dict()
    zz_audit["zz500_top_industries"] = zz_target.groupby("sw_l1_name")["target_weight_pct"].sum().sort_values(ascending=False).to_dict()

    audit_path = OUT_DIR / "live_m4_20261125_audit.json"
    audit_path.write_text(json.dumps({"hs300": hs_audit, "zz500": zz_audit}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    print("HS300 audit:", json.dumps(hs_audit, ensure_ascii=False))
    print("ZZ500 audit:", json.dumps(zz_audit, ensure_ascii=False))
    print("\n=== HS300 ZH3689205 ACTIONS ===")
    print(act_df.to_string(index=False))
    print("\n=== ZZ500 INITIAL 30 ===")
    print(zz_target[["portfolio_rank", "stock_code", "stock_name", "sw_l1_name", "target_weight_pct", "m4_score", "price", "pb", "pe_ttm"]].to_string(index=False))


if __name__ == "__main__":
    main()
