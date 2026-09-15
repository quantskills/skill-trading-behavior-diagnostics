from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlparse

import numpy as np
import pandas as pd
import requests
from scipy import stats

REQUIRED = ("timestamp", "symbol", "side", "quantity", "price")
ALIASES = {
    "timestamp": {"timestamp", "datetime", "成交时间", "委托时间", "业务时间", "时间", "trade_time"},
    "date": {"date", "成交日期", "业务日期", "日期"},
    "symbol": {"symbol", "code", "证券代码", "股票代码", "合约代码", "代码"},
    "side": {"side", "direction", "买卖方向", "操作", "业务名称", "交易方向", "方向"},
    "quantity": {"quantity", "qty", "volume", "成交数量", "发生数量", "数量"},
    "price": {"price", "成交价格", "成交均价", "价格"},
    "fee": {"fee", "commission", "手续费", "佣金", "费用"},
    "trade_id": {"trade_id", "成交编号", "合同编号", "订单号", "委托编号"},
    "account_id": {"account_id", "资金账号", "账户", "账号"},
    "currency": {"currency", "币种"},
}
BUY_WORDS = {"buy", "b", "买", "买入", "证券买入", "融资买入"}
SELL_WORDS = {"sell", "s", "卖", "卖出", "证券卖出", "卖券还款"}
BROKER_HINTS = {
    "tonghuashun": {"成交编号", "证券代码", "成交均价", "买卖方向"},
    "eastmoney": {"合同编号", "证券代码", "成交价格", "业务名称"},
    "futu": {"订单号", "代码", "方向", "成交价格"},
}


class TradeSource(Protocol):
    def fetch(self) -> pd.DataFrame: ...


def _https(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("接口地址必须是无内嵌凭证的 HTTPS URL")
    return url.rstrip("/")


class PandaAISource:
    def __init__(self, base_url: str, token: str, account_id: str, session: Any = requests):
        self.base_url, self.token, self.account_id, self.session = _https(base_url), token, account_id, session

    def fetch(self) -> pd.DataFrame:
        response = self.session.get(
            f"{self.base_url}/v1/accounts/{quote(str(self.account_id), safe='')}/trades",
            headers={"Authorization": f"Bearer {self.token}"}, timeout=30, allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        return normalize(pd.DataFrame(rows), "pandaai")


class TigerSource:
    """Adapter for an authorized tigeropen trade client; no secret is persisted."""
    def __init__(self, trade_client: Any, account_id: str):
        self.client, self.account_id = trade_client, account_id

    def fetch(self) -> pd.DataFrame:
        if not hasattr(self.client, "get_filled_orders"):
            raise TypeError("Tiger client 缺少 get_filled_orders")
        rows = self.client.get_filled_orders(account=self.account_id)
        return normalize(pd.DataFrame([vars(x) if not isinstance(x, dict) else x for x in rows]), "tiger")


class EastmoneySource:
    """Adapter for an authorized Eastmoney/EMTL client supplied by the caller."""
    def __init__(self, client: Any, account_id: str):
        self.client, self.account_id = client, account_id

    def fetch(self) -> pd.DataFrame:
        for method in ("get_trades", "query_trades", "trades"):
            fn = getattr(self.client, method, None)
            if callable(fn):
                return normalize(pd.DataFrame(fn(account_id=self.account_id)), "eastmoney")
        raise TypeError("东方财富客户端未提供 get_trades/query_trades/trades")


def _read_csv(path: Path) -> pd.DataFrame:
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("文件超过 50 MB，请按年份拆分后再导入")
    last: Exception | None = None
    for enc in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except (UnicodeError, pd.errors.ParserError) as exc:
            last = exc
    raise ValueError(f"无法识别 CSV 编码或分隔符: {type(last).__name__}")


def detect_broker(columns: list[str]) -> str:
    cols = {str(c).strip() for c in columns}
    scores = {name: len(hints & cols) for name, hints in BROKER_HINTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "generic"


def parse_file(path: str | Path) -> tuple[pd.DataFrame, str]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        raw = _read_csv(path)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path)
    else:
        raise ValueError("只支持 CSV、XLSX 和 XLS")
    broker = detect_broker(list(raw.columns))
    return normalize(raw, broker), broker


def normalize(raw: pd.DataFrame, source: str = "generic") -> pd.DataFrame:
    inverse = {alias.lower(): canonical for canonical, aliases in ALIASES.items() for alias in aliases}
    renamed = {c: inverse.get(str(c).strip().lower(), str(c).strip()) for c in raw.columns}
    data = raw.rename(columns=renamed).copy()
    if "timestamp" not in data and "date" in data:
        data["timestamp"] = data["date"]
    missing = [c for c in REQUIRED if c not in data]
    if missing:
        raise ValueError(f"缺少必要字段: {', '.join(missing)}")
    side = data["side"].astype(str).str.strip().str.lower()
    data["side"] = np.where(side.isin(BUY_WORDS), "BUY", np.where(side.isin(SELL_WORDS), "SELL", ""))
    if (data["side"] == "").any():
        bad = sorted(side[data["side"] == ""].unique())[:5]
        raise ValueError(f"无法识别买卖方向: {bad}")
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    for c in ("quantity", "price", "fee"):
        if c not in data:
            data[c] = 0.0
        data[c] = pd.to_numeric(data[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    if data[["timestamp", "quantity", "price"]].isna().any().any():
        raise ValueError("时间、数量或价格包含无法解析的值")
    if (data[["quantity", "price"]] <= 0).any().any():
        raise ValueError("数量和价格必须大于零")
    data["symbol"] = data["symbol"].astype(str).str.strip().str.upper()
    data["source"] = source
    if "trade_id" not in data:
        data["trade_id"] = [f"{source}-{i+1}" for i in range(len(data))]
    if "account_id" not in data:
        data["account_id"] = "default"
    return data[["trade_id", "account_id", "timestamp", "symbol", "side", "quantity", "price", "fee", "source"]].sort_values("timestamp").reset_index(drop=True)


def fifo_round_trips(trades: pd.DataFrame) -> pd.DataFrame:
    lots: dict[str, list[dict[str, Any]]] = {}
    closed: list[dict[str, Any]] = []
    for row in trades.itertuples(index=False):
        book = lots.setdefault(row.symbol, [])
        signed = row.quantity if row.side == "BUY" else -row.quantity
        while book and signed and math.copysign(1, signed) != math.copysign(1, book[0]["qty"]):
            lot = book[0]
            qty = min(abs(signed), abs(lot["qty"]))
            direction = 1 if lot["qty"] > 0 else -1
            pnl = qty * direction * (row.price - lot["price"])
            closed.append({"symbol": row.symbol, "open_time": lot["time"], "close_time": row.timestamp,
                           "holding_days": max((row.timestamp - lot["time"]).total_seconds() / 86400, 0),
                           "quantity": qty, "pnl": pnl - float(row.fee or 0)})
            lot["qty"] -= direction * qty
            signed += direction * qty
            if abs(lot["qty"]) < 1e-12:
                book.pop(0)
        if abs(signed) > 1e-12:
            book.append({"qty": signed, "price": row.price, "time": row.timestamp})
    return pd.DataFrame(closed, columns=["symbol", "open_time", "close_time", "holding_days", "quantity", "pnl"])


@dataclass
class Finding:
    score: int
    severity: str
    evidence: dict[str, Any]
    suggestion: str
    confidence: str = "正常"


def _severity(score: float) -> tuple[int, str]:
    value = int(np.clip(round(score), 0, 100))
    return value, "轻度" if value < 35 else "中度" if value < 70 else "重度"


def diagnose(trades: pd.DataFrame, market: pd.DataFrame | None = None, annual_turnover_benchmark: float = 4.0, average_equity: float | None = None) -> dict[str, Finding]:
    trips = fifo_round_trips(trades)
    wins, losses = trips[trips.pnl > 0], trips[trips.pnl < 0]
    win_days = float(wins.holding_days.mean()) if len(wins) else math.nan
    loss_days = float(losses.holding_days.mean()) if len(losses) else math.nan
    effect = (loss_days - win_days) / max(abs(win_days), 1.0) if np.isfinite(win_days + loss_days) else 0.0
    pvalue = float(stats.ttest_ind(losses.holding_days, wins.holding_days, equal_var=False, alternative="greater").pvalue) if len(wins) >= 2 and len(losses) >= 2 else math.nan
    s, sev = _severity(50 * max(effect, 0) + (25 if np.isfinite(pvalue) and pvalue < .05 else 0))
    disposition = Finding(s, sev, {"winning_mean_days": win_days, "losing_mean_days": loss_days, "pvalue": pvalue, "closed_lots": len(trips)}, "为每笔交易预先写下止盈、止损和最长持有期；不要在持仓后临时放宽亏损边界。")

    span = max((trades.timestamp.max() - trades.timestamp.min()).days, 1)
    notional = float((trades.quantity * trades.price).sum())
    equity_proxy = float(average_equity) if average_equity and average_equity > 0 else float((trades.quantity * trades.price).median()) or 1.0
    turnover = 0.5 * notional / equity_proxy * 365 / span
    s, sev = _severity(50 * turnover / max(annual_turnover_benchmark, .01))
    overtrade = Finding(s, sev, {"annualized_turnover": turnover, "benchmark": annual_turnover_benchmark, "days": span, "equity_basis": "provided_average_equity" if average_equity else "median_trade_notional_proxy"}, "设定每周交易次数和换手预算；只有新信息足以改变原假设时才允许加仓或换仓。", "正常" if average_equity else "较低：缺少账户平均净值")

    chase_evidence: dict[str, Any] = {"lookback_days": 5, "matched": 0}
    chase_raw = 0.0
    if market is not None and len(market):
        m = market.copy()
        m["date"] = pd.to_datetime(m["date"])
        m["return"] = pd.to_numeric(m["return"], errors="coerce")
        m = m.sort_values(["symbol", "date"])
        m["prior_return"] = m.groupby("symbol")["return"].transform(lambda x: x.rolling(5).sum().shift(1))
        joined = pd.merge_asof(trades.sort_values("timestamp"), m.rename(columns={"date": "timestamp"}).sort_values("timestamp"), on="timestamp", by="symbol", direction="backward")
        buy = joined.loc[joined.side == "BUY", "prior_return"].dropna()
        sell = joined.loc[joined.side == "SELL", "prior_return"].dropna()
        chase_raw = max(float(buy.mean()) if len(buy) else 0, 0) + max(-(float(sell.mean()) if len(sell) else 0), 0)
        chase_evidence = {"lookback_days": 5, "buy_prior_return": float(buy.mean()) if len(buy) else math.nan, "sell_prior_return": float(sell.mean()) if len(sell) else math.nan, "matched": len(buy)+len(sell)}
    s, sev = _severity(chase_raw * 1000)
    chasing = Finding(s, sev if market is not None and len(market) else "证据不足", chase_evidence, "把入场条件写成价格无关的检查表，并为连续上涨后的买入设置冷静期；卖出前先复核基本假设是否真的改变。", "正常" if market is not None and len(market) else "不足：未提供独立行情")

    sequence = trades.copy()
    sequence["notional"] = sequence.quantity * sequence.price
    close_loss_times = trips.loc[trips.pnl < 0, "close_time"].sort_values()
    next_sizes = []
    for t in close_loss_times:
        future = sequence[sequence.timestamp > t]
        if len(future): next_sizes.append(float(future.iloc[0].notional))
    avg = float(sequence.notional.mean()) or 1.0
    ratio = float(np.mean(next_sizes) / avg) if next_sizes else 1.0
    s, sev = _severity(max(ratio - 1, 0) * 80)
    gambler = Finding(s, sev, {"next_trade_size_ratio": ratio, "loss_events_with_next_trade": len(next_sizes)}, "亏损后下一笔交易不得超过常规仓位；连续亏损达到预设次数时暂停交易并复盘。")
    return {"disposition_effect": disposition, "overtrading": overtrade, "chasing": chasing, "gambler_effect": gambler}


def profile(findings: dict[str, Finding]) -> str:
    scores = {k: v.score for k, v in findings.items()}
    if max(scores.values(), default=0) < 35: return "纪律型"
    if scores["gambler_effect"] >= 70: return "赌徒型"
    if scores["overtrading"] >= 70: return "激进型"
    return "情绪型"


def write_report(trades: pd.DataFrame, findings: dict[str, Finding], out: Path, history: Path | None = None, include_identifiers: bool = False) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    record = {"timestamp": now, "scores": {k: v.score for k, v in findings.items()}, "profile": profile(findings)}
    trend = "首次诊断"
    if history:
        history.parent.mkdir(parents=True, exist_ok=True)
        previous = [json.loads(x) for x in history.read_text(encoding="utf-8").splitlines() if x.strip()] if history.exists() else []
        if previous:
            old = np.mean(list(previous[-1]["scores"].values())); new = np.mean(list(record["scores"].values()))
            trend = f"综合偏差较上次{'下降' if new < old else '上升'} {abs(new-old):.1f} 分"
        with history.open("a", encoding="utf-8") as fh: fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    labels = {"disposition_effect":"处置效应", "overtrading":"过度交易", "chasing":"追涨杀跌", "gambler_effect":"赌徒效应"}
    lines = ["# 交易行为诊断报告", "", f"- 交易记录：{len(trades)} 笔", f"- 时间范围：{trades.timestamp.min()} 至 {trades.timestamp.max()}", f"- 行为画像：**{profile(findings)}**", f"- 趋势：{trend}", "", "## 诊断结果", "", "| 项目 | 得分 | 程度 | 证据质量 |", "|---|---:|---|---|"]
    for key, item in findings.items(): lines.append(f"| {labels[key]} | {item.score} | {item.severity} | {item.confidence} |")
    for key, item in findings.items():
        lines += ["", f"### {labels[key]}", "", f"证据：`{json.dumps(item.evidence, ensure_ascii=False, default=str)}`", "", f"建议：{item.suggestion}"]
    lines += ["", "> 评分用于自我复盘，不是医学或心理诊断，也不构成投资建议。样本过少、缺少账户净值或行情时，部分指标只能作为提示。"]
    path = out / "behavior_report.md"; path.write_text("\n".join(lines)+"\n", encoding="utf-8")
    export = trades if include_identifiers else trades.drop(columns=["trade_id", "account_id"], errors="ignore")
    (out / "normalized_trades.csv").write_text(export.to_csv(index=False), encoding="utf-8-sig")
    (out / "diagnosis.json").write_text(json.dumps({k: asdict(v) for k,v in findings.items()} | {"profile": profile(findings)}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="交易心理与行为金融诊断")
    p.add_argument("--trades", required=True, help="券商 CSV/XLSX 文件")
    p.add_argument("--market", help="可选行情文件，字段 date,symbol,return")
    p.add_argument("--output", default="outputs/behavior")
    p.add_argument("--history", help="可选趋势文件；只有明确希望保留历次结果时才传入")
    p.add_argument("--include-identifiers", action="store_true", help="在标准化文件中保留成交号和账户号（默认删除）")
    p.add_argument("--turnover-benchmark", type=float, default=4.0)
    p.add_argument("--average-equity", type=float, help="账户期间平均净值；不提供时换手率只能使用代理分母")
    args = p.parse_args(argv)
    trades, broker = parse_file(args.trades)
    market = _read_csv(Path(args.market)) if args.market else None
    findings = diagnose(trades, market, args.turnover_benchmark, args.average_equity)
    report = write_report(trades, findings, Path(args.output), Path(args.history) if args.history else None, args.include_identifiers)
    print(f"识别格式：{broker}\n报告：{report}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
