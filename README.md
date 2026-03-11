# PurchasePro

面向指定商品页面的库存监控 MVP（MySQL 持久化版）。

当前默认监控你提供的商品 URL：
`https://rtjgfsc.rtjzj.com/pages/fl/shopDetail/shopDetail?id=1346&product_type=0`

## 功能

- Playwright 定时抓取商品页（名称、价格、库存文本）
- 将每次抓取快照写入 MySQL `product_snapshots`
- 当库存状态变化时写入 `stock_events`
- 支持通过 `.env` 调整轮询频率和选择器

> 建议用途：库存预警和半自动流程。请遵守目标站点服务条款。

## 目录结构

- `main.py`：启动入口
- `purchase_pro/config.py`：配置加载
- `purchase_pro/db.py`：MySQL 读写
- `purchase_pro/monitor.py`：页面抓取 + 库存状态判定
- `schema.sql`：数据库建表脚本
- `.env.example`：环境变量模板

## 快速开始

1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

2. 初始化 MySQL

```bash
mysql -u root -p < schema.sql
```

3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填写 MYSQL_PASSWORD
```

4. 运行

```bash
python main.py
```

## 后续迭代建议

- 增加通知通道（企业微信机器人/Telegram）
- 增加“价格阈值”触发规则
- 为 selectors 做站点定制配置
- 增加失败重试与健康检查
