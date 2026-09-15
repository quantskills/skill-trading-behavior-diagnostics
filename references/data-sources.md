# 数据接入

统一成交表至少需要 `timestamp / symbol / side / quantity / price`。解析器内置常见中文别名，可识别同花顺、东方财富、富途和通用表格；无法确定买卖方向时会停止，不会静默猜测。

PandaAI 适配器的契约路径为 `/v1/accounts/{account_id}/trades`，只接受 HTTPS 和 Bearer token。该路径不是公开 PandaData 行情 SDK 的接口，必须由 PandaAI 服务方确认后才可使用。配置由调用方传入 `base_url / token / account_id`，不要写进 Skill、命令历史或报告。若服务方路径不同，应在适配层修改并先跑沙箱健康检查。

老虎证券适配器接收已配置的客户端并调用 `get_filled_orders`。东方财富适配器接收调用方提供的授权客户端，依次寻找 `get_trades`、`query_trades` 或 `trades`。这两类连接应先在券商沙箱验证字段，再进入正式账户。

实际可用顺序：券商导出文件可直接使用；老虎证券需用户在本机完成 tigeropen 授权；东方财富需用户提供其账户已获准使用的交易客户端；PandaAI 需服务方提供个人成交 HTTPS 地址、访问令牌和账户号。任一 API 缺少这些信息时，程序应明确提示并回退到文件导入，不能声称已直连。

行情文件用于追涨杀跌诊断，字段为 `date / symbol / return`，其中 `return` 是当日简单收益率。
