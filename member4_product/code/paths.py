# -*- coding: utf-8 -*-
"""
组员4 统一路径解析器（自动兼容整理后的分组目录、平铺目录与 GitHub 复现结构）。
支持 v2（历史冻结快照）与 v3（PRD 3.0 跨组接口契约）无缝切换。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

MEMBER4_DIR = Path(__file__).resolve().parent.parent


def _find_workspace_root() -> Path:
    """定位 `大作业/` 或 `csi300-quant-strategy/` 根目录。"""
    p = MEMBER4_DIR.parent
    if p.name == "02_组员4_工作区":
        return p.parent
    return p


WORKSPACE_ROOT = _find_workspace_root()
UPSTREAM_ROOT = WORKSPACE_ROOT / "01_组员上游交付"


def _first_existing(candidates: list[Path], fallback: Path) -> Path:
    for cand in candidates:
        if cand.exists():
            return cand
    return fallback


def resolve_data_processed(override: Optional[str | Path] = None, prefer_tushare: bool = True) -> Path:
    """解析组员 1 数据 processed/ 目录。默认优先使用全组锁定的 Tushare 数据 3.0。"""
    if override is not None:
        return Path(override).expanduser().resolve()

    baostock_cands = [
        UPSTREAM_ROOT / "组员1_数据" / "quant_project" / "quant_project_data" / "processed",
        WORKSPACE_ROOT / "quant_project_v3" / "processed",
        WORKSPACE_ROOT / "quant_project" / "quant_project_data" / "processed",
    ]
    tushare_cands = [
        WORKSPACE_ROOT / "member1_data" / "tushare_data" / "hs300" / "processed",
        UPSTREAM_ROOT / "组员1_数据" / "Tushare_双股票池完整数据与代码" / "tushare_data" / "hs300" / "processed",
        WORKSPACE_ROOT / "Tushare_双股票池完整数据与代码" / "tushare_data" / "hs300" / "processed",
    ]
    ordered = (tushare_cands + baostock_cands) if prefer_tushare else (baostock_cands + tushare_cands)
    return _first_existing(ordered, ordered[0])


def resolve_tushare_pool_processed(pool: str = "hs300") -> Path:
    """解析 Tushare 双股票池重建包中指定池（hs300 / zz500）的 processed/ 目录。"""
    cands = [
        WORKSPACE_ROOT / "member1_data" / "tushare_data" / pool / "processed",
        UPSTREAM_ROOT / "组员1_数据" / "Tushare_双股票池完整数据与代码" / "tushare_data" / pool / "processed",
        WORKSPACE_ROOT / "Tushare_双股票池完整数据与代码" / "tushare_data" / pool / "processed",
    ]
    return _first_existing(cands, cands[0])


def resolve_member1_metadata(pool: str = "hs300") -> Path:
    """解析组员 1 双池构建元数据 JSON（兼容 GitHub 仓库 metadata/ 与工作区 processed/）。"""
    cands = [
        WORKSPACE_ROOT / "member1_data" / "metadata" / f"{pool}_RUN_METADATA.json",
        UPSTREAM_ROOT / "组员1_数据" / "Tushare_双股票池完整数据与代码" / "tushare_data" / pool / "processed" / "RUN_METADATA.json",
        WORKSPACE_ROOT / "Tushare_双股票池完整数据与代码" / "tushare_data" / pool / "processed" / "RUN_METADATA.json",
    ]
    return _first_existing(cands, cands[0])


def resolve_tushare_hs300_processed() -> Path:
    return resolve_tushare_pool_processed("hs300")


def resolve_member2_tushare_pool(pool: str = "hs300") -> Path:
    """解析组员 2 最新 Tushare 双池交付目录 member2_signals/{hs300,zz500} 或 member2_tushare/{hs300,zz500}。"""
    cands = [
        WORKSPACE_ROOT / "member2_signals" / pool,
        UPSTREAM_ROOT / "组员2_因子与信号" / "member2_tushare" / pool,
        WORKSPACE_ROOT / "member2_tushare" / pool,
    ]
    return _first_existing(cands, cands[0])


def resolve_member2_dir(version: str = "v2", override: Optional[str | Path] = None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    if version == "v3":
        cands = [
            UPSTREAM_ROOT / "组员2_因子与信号" / "member2_v3",
            WORKSPACE_ROOT / "member2_v3",
        ]
    else:
        cands = [
            UPSTREAM_ROOT / "组员2_因子与信号" / "member2_v2",
            WORKSPACE_ROOT / "member2_v2",
        ]
    return _first_existing(cands, cands[0])


def resolve_alpha101_rescreen_dir(override: Optional[str | Path] = None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    cands = [
        UPSTREAM_ROOT / "组员2_因子与信号" / "沪深300_Alpha101全量重筛",
        WORKSPACE_ROOT / "沪深300_Alpha101全量重筛",
    ]
    return _first_existing(cands, cands[0])


def resolve_member3_dir(version: str = "v2", override: Optional[str | Path] = None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    if version == "v3":
        cands = [
            WORKSPACE_ROOT / "member3_backtest",
            UPSTREAM_ROOT / "组员3_回测与归因" / "member3_v3",
            WORKSPACE_ROOT / "member3_v3",
        ]
    else:
        cands = [
            UPSTREAM_ROOT / "组员3_回测与归因" / "member3",
            WORKSPACE_ROOT / "member3",
        ]
    return _first_existing(cands, cands[0])


# 便捷默认常量（供现有 v2 脚本直接导入，零破坏性）
PROC = resolve_data_processed()
M2_DIR = resolve_member2_dir("v2")
M2_SIG = M2_DIR / "signals"
M2_RES = M2_DIR / "results"
M3_DIR = resolve_member3_dir("v2")
M3_RES = M3_DIR / "results"
ALPHA101_DIR = resolve_alpha101_rescreen_dir()
