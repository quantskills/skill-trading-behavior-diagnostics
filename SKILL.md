---
name: trading-behavior-diagnostics
description: Analyze a trader's own execution history for disposition effect, overtrading, return chasing, and loss-driven position escalation. Use when the user provides a PandaAI account, supported broker connection, or broker export and wants a behavioral report rather than market analysis.
---

# 交易心理与行为诊断

把不同来源的成交记录整理成统一格式，再生成四项行为偏差评分、交易者画像、改进建议和历次变化。结果用于交易复盘，不作医学、心理或投资诊断。

## 工作方式

1. 确认数据来自 PandaAI、券商授权客户端或券商导出文件。
2. 若为文件，直接运行解析器；不要要求用户改列名。若识别失败，列出缺失字段和已识别字段。
3. 若为 API，只在用户明确授权后连接。凭证从环境变量或调用方安全存储读取，不写入报告和仓库。
4. 标准化后检查时间、代码、买卖方向、数量、价格和重复成交编号。
5. 运行四项诊断并披露样本量。缺少行情时，将追涨杀跌标为证据不足，不凭成交价猜测市场涨跌。
6. 输出 Markdown、JSON、标准化成交表；用户同意保存历史时再写入趋势文件。
7. 首次使用先运行启动检查。未验证的 API 只能标为“待接入”，文件模式不受影响。

## 命令

```powershell
python scripts\behavior_tool.py --trades data\broker.csv --market data\market_returns.csv --output outputs\behavior
python scripts\healthcheck.py --sample data\broker.csv
```

文件识别、API 适配和标准字段见 [数据接入](references/data-sources.md)；统计口径见 [诊断方法](references/methodology.md)。

## 解释边界

- 处置效应以已平仓批次的盈亏与持有期比较为依据，样本不足时不下显著性结论。
- 换手率若没有逐日净值，只能使用成交额代理，并明确标注。
- 追涨杀跌需要独立行情收益数据。
- “赌徒效应”只描述亏损后放大仓位的交易序列，不判断人格。
- 评分是可解释的复盘量表，不是临床量表，也不保证行为与亏损之间存在因果关系。
