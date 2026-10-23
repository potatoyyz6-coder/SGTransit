# SGTransit：简历项目说明与后续规划

初次整理：2026-10-13；发布文案更新：2026-10-23。以下已完成功能以 v0.1.0 为准，后续规划不计入当前成果。

## 1. 可直接用于中文简历的版本

### SGTransit｜公交候选路线与换乘可靠性研究

**个人研究项目，与 OpenAI Codex 协作开发**

**技术栈：** Python、NetworkX、NumPy、Matplotlib、pytest、JavaScript、GitHub Actions

**时间：** 2026.09–2026.10（v0.1.0）

**源码仓库：** [potatoyyz6-coder/SGTransit](https://github.com/potatoyyz6-coder/SGTransit)

- 从新加坡公交长间隔、换乘不确定性和站外等待体验出发，定义多路线备选需求，与 Codex 共同构建公交路径搜索、随机模拟和本地交互原型。
- 基于有向线路站序、反向乘车时间下界和有界搜索生成路线候选，支持比较同车继续与沿途换乘；在一个 25 站局部案例中生成 7,212 条拓扑候选，其中 4,558 条满足默认参考筛选条件。
- 建立固定路线、先到先乘与后续路径评分策略的合成对照实验，分离策略选择与评估样本，使用每策略 10,000 次留出模拟比较均值、P95 和站外等待，同时保留无收益及不利场景。
- 交付支持两个案例的本地 Web 界面、可复现实验报告及 256 项自动化测试；配置 Windows/Linux、Python 3.10/3.12 四组 CI 并通过验证，区分历史拓扑、ETA 预测与实际出行结果。

上述表述描述共同开发的项目成果，不表示全部代码由本人独立编写。提交简历前，应确认能解释所列模块、指标及局限；没有掌握的细节应删减，不把 Codex 的工作写成独立完成。

### 篇幅紧张时的三条版

**SGTransit｜公交路线与换乘策略研究｜与 OpenAI Codex 协作开发**

- 提出低频公交多备选换乘问题，结合有向图搜索、历史站序与随机等待模型，构建候选路线及途中继续乘坐/换乘的本地研究原型。
- 通过固定路线与动态备选策略的 10,000 次留出模拟比较平均耗时、P95 和等待时间，保留相关到站、绕行和无收益反例，不将模型结果当作实际提速。
- 实现两个案例的可视化查询与可复现实验；256 项测试通过，完成 Windows/Linux × Python 3.10/3.12 CI 验证。

## 2. 英文简历版本

### SGTransit | Bus Routing and Transfer Reliability Research

**Personal research project, developed in collaboration with OpenAI Codex**

**Stack:** Python, NetworkX, NumPy, Matplotlib, pytest, JavaScript, GitHub Actions

**Period:** Sep–Oct 2026 (v0.1.0)

- Initiated a bus-transfer research project based on Singapore commuting scenarios; defined requirements and worked with OpenAI Codex on routing, simulation, and a local reference interface.
- Built directed route-candidate search with reverse travel-time lower bounds and bounded exploration; modeled staying onboard versus transferring, generating 7,212 topology candidates in a 25-stop case, with 4,558 eligible under declared reference assumptions.
- Evaluated fixed-route and adaptive policies on 10,000 held-out Monte Carlo trials per strategy, comparing mean duration, P95, and station waiting while retaining counterexamples and no-benefit scenarios.
- Delivered a two-case local web interface, reproducible reports, and 256 automated tests; validated CI across Windows/Linux and Python 3.10/3.12 without treating ETA forecasts as observed journey outcomes.

## 3. 与 Codex 的协作说明

推荐在简历项目标题或角色行保留：**“与 OpenAI Codex 协作开发”**。不要只在仓库角落标注，也不必在每一条中重复。

| 分工 | 本项目中可以确认的贡献 |
| --- | --- |
| 本人 | 提出公交换乘痛点与项目目标；提供实际通勤候选走法并纠正遗漏；提出少等待、保留多个备选和同车继续的需求；提供少量人工地图参考并推动实验与使用流程迭代 |
| OpenAI Codex | 协助建模和方案分析；编写与修改代码；执行测试、实验、界面验证；整理文档与发布流程 |
| 共同迭代 | 根据具体案例调整需求和实现范围，区分模型估计、预测证据与实际结果，保留失败或证据不足的实验结果 |

不建议使用“独立从零完成全部算法和代码”“独立发明 Hyperpath 算法”或“所有代码均已由本人逐行审计”等没有事实依据的表述。

## 4. 可核查成果与口径

| 成果 | 可以怎么说 | 不能引申成什么 |
| --- | --- | --- |
| 25 站 Blk 18 → CDE 案例，7,212 条拓扑候选、4,558 条默认合格候选 | 在声明的局部路网、历史运营窗口与搜索约束下自动生成候选 | 7,212 条不同服务组合、全岛覆盖、全部当前可乘 |
| 10,000 次留出模拟 | 合成模型中的可复现策略比较，选择样本与评估样本分离 | 10,000 次真实乘车、10,000 名用户或线上 A/B 测试 |
| 256 项测试与四组 CI | 发布时验证了模型、搜索、证据边界和接口等自动化行为 | 线上零故障、算法全局最优或全场景安全 |
| 两个固定案例的本地界面 | 能选择案例、检查路线变体并比较途中备选；可明确确认后查询 ETA | 任意地址导航、全岛规划器、始终在线的公共服务 |
| LTA 到站预测记录及分析 | 获取和分析预测，缺失时保留有标签的模型参考 | 已观测到车辆实际到站、已校准赶车成功率 |

### 可选的实验数字

在 `independent_alternatives` **合成场景**中，后续评分策略相对固定均值基线的平均耗时由 33.04 降至 27.02 分钟，P95 由 43.16 降至 34.49 分钟，即约减少 8.7 分钟的 P95。

该场景中先到先乘策略也达到相同结果；在同步到站场景中没有观察到这项收益。因此不能把这个例子写成“新算法普遍降低 20% 延误”或“比 Google Maps 快”。简历正文优先使用实验设计与工程验证数字；若使用性能数字，必须保留“合成场景”和基线名称。

证据入口：

- [发布验证记录](RELEASE_VERIFICATION.md)
- [公平合成基准报告](../results/fair_benchmark/report.md)
- [合成基准验证与样本配置](../results/fair_benchmark/verification.md)
- [Blk 18 → CDE 案例报告](../results/blk18_cde_reference/report.md)
- [当前界面与运行方法](../README.md)
- [v0.1.0 版本](https://github.com/potatoyyz6-coder/SGTransit/releases/tag/v0.1.0)
- [发布提交的 GitHub CI](https://github.com/potatoyyz6-coder/SGTransit/actions/runs/38232341763)

本次整理没有重跑全部实验；以上数字来自已保存、已发布的 v0.1.0 验证记录。

## 5. 公开源码的定位与边界

**建议：如果希望把 GitHub 链接放进投递简历，公开一个经过检查、定位清楚的研究版本更方便读者核查；不必等到通用导航完成。公开不是写进简历的前提。**

此次发布面向源码和研究成果展示，不部署在线导航服务。2026-10-23 的发布前检查见
[检查记录](PUBLICATION_AUDIT_20261023.md)；该文记录的是当时的私有快照，实际访问状态以 GitHub 为准。

公开前还应确认：

1. 不仅检查当前文件，还检查提交历史、Actions 日志和附件是否存在凭据、个人信息或不应再分发的内容。已有轻量发布检查不能替代完整安全审计。
2. 保留 MIT 代码许可证、独立的数据/图标归属和项目免责声明，不将 LTA 数据误称为 MIT 数据。
3. 明确写出“两个固定案例、本地研究界面、历史数据与模型估计”，避免造成完整导航产品的印象。
4. 接受他人按许可证查看、复制和使用代码；公开源代码与部署面向公众的导航服务是两件事，后者仍需单独产品及法律/隐私评审。
5. 发布前复查当前提交及新的 CI 日志；公开后用未登录方式确认仓库和简历文档可访问。

GitHub 官方说明：私有转公开后代码、Actions 历史和日志可被公众访问，其他人可以 fork；再次转私有不会使已存在的公开 fork 一起变为私有。参见 [GitHub 仓库可见性说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)。

## 6. 自定义起终点的复杂程度

必须区分“在已经加载的路网中自选站点”和“自动支持新加坡任意站点”。当前算法函数可接收起终点，但界面与建网入口选择了固定案例线路。仅增加输入框不能使未加载的线路自动参与规划。

| 范围 | 相对难度 | 主要工作 |
| --- | --- | --- |
| 已有案例路网内自选公交站 | 中等，最适合下一步 | 站名/站号搜索、起终点校验、出发时间、通用查询状态；修改按案例缓存的候选与途中逻辑，保持搜索边界清楚 |
| 本地历史数据中任意公交站之间自动搜索 | 中高 | 通用方向/站序导入、环线与重复停站处理、目标相关索引、有界候选搜索、性能与覆盖测试；不能把全网完整路径都枚举出来 |
| 任意地址/建筑物/地图点的门到门规划 | 高，属于新增子系统 | 地址解析、附近站点匹配、真实可通行的步行连接、跨街/校园入口、起终点接驳及许可核查；不能用直线距离替代可走路线 |
| 上述功能再结合即时 ETA | 额外增加工作 | 只为有限候选查询相关站点、限制请求量、缓存时效、方向匹配和缺失降级；不能对全岛每站逐一调用 API |

这是基于当前代码的工程判断，不是经过性能原型验证的工期承诺。现有局部路网内自选站点通常是数天级实现与回归任务；通用建网与搜索应按数周级迭代考虑，环线、性能或步行数据问题可能扩大范围。具体排期应先以一个不在原案例中的站点对验证。

主要依据：

- [固定案例入口](../experiments/local_planner.py)：`CASES`、`case_data()` 以及后续路径状态依赖案例路网。
- [通用搜索函数](../src/sg_transit/routing.py)：接受不同起终点，已有约束、反向下界和搜索预算，但仍有候选枚举成本。
- [线路模型](../src/sg_transit/models.py)：当前拒绝同一服务模式中出现重复站点。扩大全网时，需要处理访问次序和同车身份，不能直接拆段后重复计等待/换乘。

### 推荐下一版验收

1. 支持按站名或站号自选起终点，并显示支持的网络范围。
2. 不调用 API 也能生成带来源说明的候选、换乘站和时间拆分。
3. 保留原来两个案例作为回归测试，增加多个未手工编写答案的站点对。
4. 明确区分不在覆盖范围、在声明路网中不可达、预算截断以及运营状态未知。
5. 途中选择继续保留历史乘车状态，同车继续不重复收费式地累计等待和换乘。

这些都是**后续规划，尚未实现**，不能提前写进简历的已完成部分。

## 7. 面试介绍与准备

### 一分钟介绍

> 我在新加坡通勤时发现，只给出一条预计最快路线，不能很好地表达低频公交错过换乘后的等待代价。我提出了这个问题，并与 OpenAI Codex 协作开发 SGTransit：先在合成网络和局部历史公交网络中生成候选，再比较固定路线、先到先乘和考虑后续路径的策略。系统会区分继续坐同一辆车与下车换乘，也区分模型时间、ETA 预测和实际结果。当前有两个本地交互案例、可复现实验与 256 项测试，跨平台 CI 已通过；尚未实现全岛任意站点或地址导航。我的贡献主要是需求定义、真实案例反馈和实验方向迭代，Codex 协助完成代码、测试与文档。

应能解释的问题：

- 为什么平均耗时相近时仍需要比较 P95、换乘缓冲和站外等待？
- 为什么可选服务多不一定更快，车辆同步到站或绕行会怎样改变结果？
- 同车继续为什么不能算作新的上车等待和换乘？
- 为什么使用独立的策略选择样本与留出评估样本？
- 为什么预测 ETA 的变化不等于实际到站误差，也不能直接换算成赶车成功率？
- 搜索预算、局部覆盖和固定案例有哪些限制？哪些代码与判断由本人完成，哪些由 Codex 辅助？

本项目能作为研究与工程实践经历，但不应包装成已被采用的商业产品、学术原创成果或拥有真实用户规模的线上服务。

> This project is an independent research project and is not affiliated with,
> endorsed by, or sponsored by the Land Transport Authority of Singapore,
> Google, or Citymapper.
