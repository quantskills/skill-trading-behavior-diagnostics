import pandas as pd
import pytest

from scripts.behavior_tool import EastmoneySource, PandaAISource, TigerSource, detect_broker, diagnose, fifo_round_trips, normalize, parse_file, write_report


def sample():
    return normalize(pd.DataFrame({
        "成交时间": ["2024-01-01", "2024-01-03", "2024-01-04", "2024-02-20", "2024-02-21"],
        "证券代码": ["AAA", "AAA", "BBB", "BBB", "CCC"],
        "买卖方向": ["买入", "卖出", "买入", "卖出", "买入"],
        "成交数量": [100, 100, 100, 100, 300], "成交价格": [10, 12, 10, 8, 5],
    }), "tonghuashun")


def test_normalize_and_fifo():
    trades = sample(); trips = fifo_round_trips(trades)
    assert list(trades.side[:2]) == ["BUY", "SELL"]
    assert list(trips.pnl) == [200, -200]
    assert trips.iloc[1].holding_days > trips.iloc[0].holding_days


def test_diagnosis_has_four_bounded_scores():
    result = diagnose(sample(), annual_turnover_benchmark=10)
    assert set(result) == {"disposition_effect", "overtrading", "chasing", "gambler_effect"}
    assert all(0 <= x.score <= 100 for x in result.values())


def test_broker_detection():
    assert detect_broker(["成交编号", "证券代码", "成交均价", "买卖方向"]) == "tonghuashun"
    assert detect_broker(["合同编号", "证券代码", "成交价格", "业务名称"]) == "eastmoney"
    assert detect_broker(["订单号", "代码", "方向", "成交价格"]) == "futu"


class Client:
    def get_filled_orders(self, account): return [{"timestamp":"2024-01-01", "symbol":"A", "side":"BUY", "quantity":1, "price":1}]
    def query_trades(self, account_id): return [{"timestamp":"2024-01-01", "symbol":"A", "side":"BUY", "quantity":1, "price":1}]


def test_injected_broker_clients():
    assert len(TigerSource(Client(), "x").fetch()) == 1
    assert len(EastmoneySource(Client(), "x").fetch()) == 1


def test_rejects_bad_rows():
    with pytest.raises(ValueError): normalize(pd.DataFrame({"timestamp":["x"]}))
    with pytest.raises(ValueError): PandaAISource("http://unsafe.example", "secret", "a")


def test_futu_file_and_private_identifiers_are_removed(tmp_path):
    path=tmp_path/"futu.csv"
    pd.DataFrame({"订单号":["private"],"账户":["account"],"成交时间":["2024-01-01"],"代码":["A"],"方向":["买入"],"成交数量":[1],"成交价格":[2]}).to_csv(path,index=False,encoding="utf-8-sig")
    trades,broker=parse_file(path); assert broker=="futu"
    report=write_report(trades,diagnose(trades),tmp_path/"out")
    exported=pd.read_csv(report.parent/"normalized_trades.csv")
    assert "trade_id" not in exported and "account_id" not in exported
