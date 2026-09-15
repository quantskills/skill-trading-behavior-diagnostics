# 交易心理与行为金融诊断

这套工具从自己的成交记录入手，检查处置效应、过度交易、追涨杀跌和亏损后放大仓位。它会先整理不同券商的字段，再给出评分、证据、行为画像和改进建议。再次运行时，还可以比较行为变化。

适合个人交易复盘，也适合 PandaAI 或券商平台接入自己的成交数据。报告只描述交易行为，不作心理或医学诊断，也不提供买卖建议。

## 能读哪些数据

文件模式可以直接使用，支持 CSV、XLSX 和 XLS。解析器会识别同花顺、东方财富、富途及常见通用字段，不要求先手工改列名。

老虎证券可传入已经授权的 `tigeropen` 客户端。东方财富可传入账户已有权限的交易客户端。PandaAI 预留了 HTTPS 接入方式，需要服务方提供个人成交接口地址、访问令牌和账户号。公开的 PandaData 行情接口不包含个人成交记录。

接口条件不齐时，使用券商导出文件即可完成完整诊断。详细说明见[数据接入](references/data-sources.md)。

## 安装

需要 Python 3.11 或更高版本。

```powershell
python -m pip install -r requirements.txt
```

先检查本机环境和文件是否可读。

```powershell
python scripts\healthcheck.py --sample data\trades.csv
```

## 开始诊断

准备券商导出的成交文件后运行下面的命令。

```powershell
python scripts\behavior_tool.py `
  --trades data\trades.csv `
  --output outputs\behavior
```

若有逐日行情收益，可以一并传入。这样才能判断买入前是否连续上涨、卖出前是否连续下跌。

```powershell
python scripts\behavior_tool.py `
  --trades data\trades.csv `
  --market data\market_returns.csv `
  --average-equity 500000 `
  --output outputs\behavior
```

`--average-equity` 填写统计期间的平均账户净值。省略时仍可运行，但换手率会使用成交金额代理值，报告会降低该项证据等级。

## 输出文件

- `behavior_report.md` 提供四项诊断、行为画像和改进建议
- `diagnosis.json` 便于其他程序读取结果
- `normalized_trades.csv` 保存清洗后的成交记录，默认删除账户号和成交号

如需追踪多次诊断的变化，可添加 `--history .behavior-history/history.jsonl`。程序默认不跨次保存历史。

## 试运行

仓库带有演示数据生成器，可用它检查完整流程。

```powershell
python scripts\make_demo_data.py --directory data
python scripts\behavior_tool.py `
  --trades data\tonghuashun_demo.csv `
  --market data\market_returns.csv `
  --output outputs\demo
```

评分方法和样本要求见[诊断方法](references/methodology.md)。

## 开发检查

```powershell
python -m pytest -q
python -m compileall -q scripts tests
```

本项目采用 GPL-3.0 许可证。
