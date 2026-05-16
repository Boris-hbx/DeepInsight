# ⛔ DECISIONS-REQUIRED — Cedar 闸门进 enforce 前的两个阻塞决策

> 关联:`docs/specs/001-cedar-policy-gate.md` §9 · `agent/policies/agent.cedar` 头部 sentinel
> 创建:2026-05-15 · 状态:**两项均未决,enforce 被阻塞**
>
> 这两个决策没定,以下安全性质只是半成品:
> - 「删 = 自锁」(fail-closed-on-missing)
> - 「审计篡改可检出」(哈希链)
>
> `CedarPDP`(尚未实现)启动时必须 grep `agent/policies/agent.cedar` 中的
> `UNRESOLVED-DECISION` 标记;只要还在 → **拒绝以 enforce 启动,只许 shadow**。
> 这是结构性防遗忘:决策没定,系统就进不了 enforce。解决一项后,删除
> `agent.cedar` 中对应那行 sentinel 并在下方打勾。

---

## ① TRUST_ANCHOR_LOCATION — 期望校验和(信任锚)放哪?

**为什么阻塞**:`CedarPDP` 启动时记策略文件校验和,每次决策前比对,
被删/改 → 进 deny-all-dangerous(「删=自锁」)。但**校验和本身若和策略
文件放一起,agent 两个一起删/改就绕过**,「删=自锁」失效。锚必须在
agent 不可达处。

**选项**

| 方案 | 优点 | 缺点 |
|---|---|---|
| 编译进代码常量 | 离线、零依赖 | 改策略要改代码 + 重发 |
| 环境变量注入 | 改策略不动代码 | 取决于谁能设环境(agent 能读能改?) |
| 宿主只读挂载 | 强隔离 | 需宿主/容器配合;Windows 上等价物待定 |
| 外部 KMS | 最强 | 给离线 agent 引入网络依赖(与项目「离线」取向冲突) |

**决策**:______________  **决策人**:阿宝  **日期**:______
- [ ] 已决,sentinel 已从 agent.cedar 移除

## ② AUDIT_CHAIN_HEAD_ANCHOR — 审计哈希链链头外锚到哪?

**为什么阻塞**:审计日志靠 `seq` + `prev_hash`/`hash` 哈希链做篡改检测。
root 对手能删本地文件;**唯有把链头哈希定期送到 agent 够不着处**,
删/改才"留疤可检出"。链头锚不定,「篡改可检出」只是半成品。

**选项**

| 方案 | 优点 | 缺点 |
|---|---|---|
| stderr / stdout(harness 捕获) | 零新依赖,飞出进程即不可改 | 依赖 harness/运维真的留存了输出 |
| 宿主只读路径 | 本地、强 | 需宿主配合;Windows 等价物待定 |
| off-box(远端) | 最强留证 | 引入网络依赖 |

**决策**:______________  **决策人**:阿宝  **日期**:______
- [ ] 已决,sentinel 已从 agent.cedar 移除

---

## 旁注:其它已记录但不阻塞 enforce 的开放问题

见 spec 001 §9:信任分级粒度、按工具参数约束、三态实现方式、
只读 step 故障 fail-open/closed、是否需 ADR、`agent/` 纳入 git。
这些影响完善度但不卡 enforce 门槛;上面两项才是硬阻塞。
