# PurchasePro

面向融通金商城店铺页的多商品库存监控（MySQL 持久化版）。

当前默认监控页面：
`https://rtjgfsc.rtjzj.com/pages/tabBar/shop/shop`

## 功能

- Playwright 定时抓取店铺页，按“推荐分类/黄金/白银/铂金”分类点击后抓取商品库存与价格
- **仅当库存数变化时**写入 MySQL，避免每轮全量落库
- 价格会随库存变化记录到 `product_snapshots`
- 仅处理商品名以“融通金”开头的真实商品，过滤分类标题等非商品文本
- 将库存变化事件写入 `stock_events`
- 支持通过 `.env` 调整轮询频率和选择器

## 目录结构

- `main.py`：启动入口
- `purchase_pro/config.py`：配置加载
- `purchase_pro/db.py`：MySQL 读写
- `purchase_pro/monitor.py`：页面抓取 + 多商品库存变化判定
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
# 编辑 .env 填写 MYSQL_PASSWORD 和选择器
```

4. 运行

```bash
python main.py
```

## 数据说明

- `product_snapshots`：仅存“库存变化时”的快照（含商品名、库存数、库存原文、价格）
- `stock_events`：库存变化流水（上次库存 -> 当前库存）

## 说明

- 程序会优先按 `CATEGORY_NAMES` 依次点击分类按钮（默认：推荐分类,黄金,白银,铂金）。
- 若某分类 DOM 抓取失败，会自动尝试从页面嵌入 JSON 兜底提取库存与价格。
- 若 JSON 也失败，会基于 `page.inner_text("body")` 的全文文本格式兜底解析商品名/库存/价格。
- 若首次运行未抓到商品，请先打开网页检查 DOM，再调整 `.env` 中 selectors。
- 本工具用于库存监控与提醒，请遵守目标站点服务条款。


## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```
