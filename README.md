# 交易心理与行为金融诊断

多数交易工具盯着市场，这个项目改为盯着交易者自己的执行记录。它会自动识别常见券商导出格式，整理成交记录，并检查处置效应、过度交易、追涨杀跌和亏损后放大仓位四类问题。

## 已实现的数据入口

- PandaAI：已提供 HTTPS 适配契约；服务地址、令牌和账户号齐备后才能启用，当前公开 PandaData 行情接口不包含个人成交记录
- 老虎证券：接收已经授权的 `tigeropen` 交易客户端
- 东方财富：接收调用方已经授权的交易客户端
- 文件：自动识别同花顺、东方财富、富途和通用 CSV/XLSX

API 适配器不保存密钥，也不会替用户绕过券商授权。PandaAI 与东方财富个人成交接口尚未获得可验证的正式路径，因此不能算作已打通；文件模式和调用方注入的已授权客户端可以直接使用。具体缺口与配置方式见数据接入说明。

## 输出内容

每项偏差给出 0–100 分和轻度/中度/重度标记，并附上证据与具体建议。四项结果会汇总成“纪律型、情绪型、激进型、赌徒型”画像。再次运行时可与上一次得分比较。

## 快速开始

需要 Python 3.11 或更高版本。

```powershell
python -m pip install -r requirements.txt
python scripts\healthcheck.py --sample data\tonghuashun_demo.csv
python scripts\make_demo_data.py --directory data
python scripts\behavior_tool.py `
  --trades data\tonghuashun_demo.csv `
  --market data\market_returns.csv `
  --output outputs\behavior
```

`--market` 可省略，但届时追涨杀跌只能标记为证据不足。程序默认不保存跨次历史；希望追踪变化时，显式添加 `--history .behavior-history/history.jsonl`。标准化成交表默认删除账户号和成交号，只有明确添加 `--include-identifiers` 才保留。

## 标准成交字段

| 字段 | 含义 |
|---|---|
| `timestamp` | 成交时间 |
| `symbol` | 证券代码 |
| `side` | `BUY` 或 `SELL` |
| `quantity` | 成交数量 |
| `price` | 成交价格 |
| `fee` | 手续费，可选 |

详细字段映射见 [数据接入说明](references/data-sources.md)。算法定义见 [诊断方法](references/methodology.md)。

## 验证

```powershell
python -m pytest -q
python -m compileall -q scripts tests
```

本项目只提供个人交易复盘，不构成投资建议或心理诊断。
