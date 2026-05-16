# agent/.audit/ — 审计日志主 sink(spec 001 §4.2)

> status: SCAFFOLD(占位)· 实现于 spec building 阶段

本目录是 Cedar 闸门审计日志的**主 sink**(append-only)。设计要点:

- **agent 不可达**:已纳入 `agent/policies/agent.cedar` 的不可变更红线
  (`resource.path like "agent/.audit/*"`),且在写白名单之外。被攻陷的
  工具即使能写报告,也碰不到这里。
- **log-or-deny**:`CedarPDP.decide()` 返回判定前必须写记录;所有 sink
  写失败 → 判定强制 `DENY`(记不下 = 不放行)。
- **防篡改**:每条带 `seq` + `prev_hash`/`hash` 哈希链;删/改任一条 →
  链断或缺号 → 校验暴露。链头外锚位置 = **未决决策 ②**
  (见 `agent/policies/DECISIONS-REQUIRED.md`)。
- **诚实边界**:只保证「经过 PDP 的判定」必记。绕过 PDP 的子进程
  syscall 无判定可记 —— 唯一真解是沙箱(spec 002)。

实际日志文件(`*.jsonl`)运行时生成,不入 git。
