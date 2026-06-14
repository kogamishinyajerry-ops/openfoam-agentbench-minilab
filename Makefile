# OpenFOAM-AgentBench MiniLab —— 常用一键命令
# 用法：make <目标>。venv 默认在 ./.venv，前端在 ./frontend。
PY := ./.venv/bin/python
OFAB := ./.venv/bin/ofab

.DEFAULT_GOAL := help
.PHONY: help install seed experiment test build dev api verify demo clean

help:  ## 列出所有可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## 建 venv + 装后端(含测试依赖) + 装前端依赖
	python3 -m venv .venv
	./.venv/bin/pip install -e "backend[test]"
	cd frontend && npm install

seed:  ## 生成回放数据包 + 前端数据
	$(OFAB) demo seed

experiment:  ## 跑试点实验 -> 全部 JSON 产物 + report.md
	$(OFAB) experiment experiments/pilot_001/protocol.yaml

test:  ## 跑全部测试(后端 297 个 pytest + 前端 34 个 vitest)
	$(PY) -m pytest backend
	cd frontend && npm test

build:  ## 前端生产构建
	cd frontend && npm run build

dev:  ## 启动前端看板(开发服务器 http://localhost:5173)
	cd frontend && npm run dev

api:  ## 启动看板要读的 API(http://localhost:8000)
	$(PY) -m uvicorn ofab.api:app --reload --port 8000

verify:  ## 「做完」门：后端测试 + 前端测试 + 前端构建都过
	$(PY) -m pytest backend
	cd frontend && npm test && npm run build

demo:  ## 路演用：重新 seed 后起看板
	$(OFAB) demo seed
	cd frontend && npm run dev

clean:  ## 清理生成的运行产物与缓存
	rm -rf runs backend/.pytest_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
