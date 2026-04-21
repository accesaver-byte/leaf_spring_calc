# 板簧参数计算 Web 工具 — 项目进展

## 项目背景

辰赛汽车配件公司原来用 Excel (`工作簿1.xlsx`) + 单变量求解 (Goal Seek) 进行板簧参数计算。
本项目将所有计算逻辑提取为 Python + Streamlit Web 应用，支持任意单变量反算。

## 当前状态: 核心功能已完成，待部署

### 已完成

#### 1. 计算引擎 (leaf_spring_calc.py)

5 个计算模型全部实现，且通过 Excel 原始数据验证：

| 模型 | 功能 | 对应 Excel Sheet | 验证状态 |
|------|------|-----------------|---------|
| 模型1 | 单片几何参数互算 (卷耳片/简单直片) | Sheet1 上半/下半 | 完全匹配 |
| 模型2 | 非对称板簧弧高 | Sheet1 (2) | 完全匹配 |
| 模型3 | 圆弧多片弧高计算 (支持动态片数) | Sheet1 (3)/(4)/(7) | 逐片完全匹配 |
| 模型4 | 卷耳展开/下料长度 (5种子类型) | Sheet1 (5)/(6) | 完全匹配 |
| 模型5 | 变截面总成弧高 (支持动态片数) | Sheet1 (不动)/(9)/(10) | 完全匹配 |

**关键验证数据点:**
- 模型1 卷耳片: D=560.07, H=108, r=18.5, t=10 → R=1815.617, α=18.159°, s=577.000
- 模型1 直片: D=624.79, H=59, r=0, t=16 → R=3337.618, α=10.789°, s=630.000
- 模型2: 伸直全长=1513 → R=1932.70, H短=119.09, H长=160.87
- 模型3: 11片, F1=106 → 逐片 F/C/R 全部匹配 Excel
- 模型4c 二片包耳: L1=58.905, L2=34.563, L3=27.190, L4=57.374 → 展开=666.284
- 模型5: 3片, E1=95 → 装配弧高=110, 样板弧高+卷耳=129.49

**技术细节:**
- 模型4a/4b 中 PI 使用 3.14 (与 Excel 公式保持一致)
- 模型4c/4d 中 PI 使用 3.14159 (与 Excel 公式保持一致)
- 单变量求解使用 `scipy.optimize.brentq` 数值方法

#### 2. Streamlit Web 界面

- 侧边栏选择 5 个计算模型
- 每个模型支持正向计算和单变量反算
- 模型3/5 使用 `st.data_editor` 动态编辑多片参数表格
- 模型5 支持"反算第1片弧高"模式

#### 3. 部署文件

| 文件 | 用途 |
|------|------|
| `leaf_spring_calc.py` | 主程序 (计算逻辑 + UI，单文件) |
| `requirements.txt` | Python 依赖: streamlit, scipy, numpy, pandas |
| `Procfile` | 启动命令 (Zeabur/Heroku 兼容) |
| `.streamlit/config.toml` | Streamlit 服务器配置 (headless, port 8080) |
| `.gitignore` | 忽略 Excel/Word/PDF/缓存文件 |
| `CLAUDE.md` | Claude Code 项目指引 |

#### 4. Git 仓库

- 已 `git init` 并提交首次 commit
- 未推送到远程 (GitHub 仓库尚未创建)

### 待完成

#### 部署到 Zeabur

1. **在 GitHub 创建仓库** `leaf-spring-calc` (用户名: accesaver-byte)
   - 创建空仓库 (不要勾选 README/.gitignore)
2. **推送代码:**
   ```bash
   git remote add origin https://github.com/accesaver-byte/leaf-spring-calc.git
   git push -u origin master
   ```
3. **在 Zeabur 部署:**
   - 登录 Zeabur → 创建项目 → Deploy Service → Git → 选择 GitHub 仓库
   - Zeabur 自动识别 Python 项目并安装依赖
   - 部署后在 Networking 中 Generate Domain 获取公网地址

### 可选后续改进

- [ ] 添加计算结果导出 (CSV/Excel)
- [ ] 添加板簧示意图 (matplotlib 绘图)
- [ ] 多语言支持 (中/英)
- [ ] 用户登录与计算历史保存

## 本地运行

```bash
pip install streamlit scipy numpy pandas
streamlit run leaf_spring_calc.py
# 浏览器打开 http://localhost:8501
```

## 文件结构

```
板簧计算/
├── leaf_spring_calc.py       # 主程序 (809 行)
├── requirements.txt          # Python 依赖
├── Procfile                  # 云部署启动命令
├── .streamlit/config.toml    # Streamlit 配置
├── .gitignore
├── CLAUDE.md                 # Claude Code 指引
├── progress.md               # ← 本文件
├── 工作簿1.xlsx              # 原始 Excel 计算表 (未纳入 Git)
├── 汽车钢板弹簧悬架设计.doc   # 设计参考文档 (未纳入 Git)
└── 汽车钢板弹簧悬架设计.pdf   # 设计参考文档 (未纳入 Git)
```

## 公式来源映射

| 计算函数 | Excel 公式位置 |
|---------|---------------|
| `model1_forward` | Sheet1 H5/I5/J5 (卷耳) 和 H15/I15/J15 (直片) |
| `model2_forward` | Sheet1(2) C7/C9/C10/C11 |
| `model3_forward` | Sheet1(3) C/D/E/F/H 列, 总成弧高 P2=B3²×N17/B17 |
| `model3_with_eye` | Sheet1(7) 含弧长列和卷耳修正 K18 |
| `model4a_simple_eye` | Sheet1(5) D6 |
| `model4a_quarter` | Sheet1(5) G15 |
| `model4b_arc_eye` | Sheet1(5) F24 |
| `model4c_wrap2` | Sheet1(5) F42-F47 |
| `model4d_wrap3` | Sheet1(5) F53-F58 |
| `model5_forward` | Sheet1(不动) D/E/K/L/O/P 列, 总成 K8/Q8 |
