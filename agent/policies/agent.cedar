// ════════════════════════════════════════════════════════════════════
//  agent.cedar — DeepInsight Cedar 策略闸门 (spec 001)
//  status: SCAFFOLD / DRAFT — 由 spec 001 §4.2 v3 转写
// --------------------------------------------------------------------
//  ⛔ 两个未决决策阻塞 enforce(详见同目录 DECISIONS-REQUIRED.md):
//
//  UNRESOLVED-DECISION: TRUST_ANCHOR_LOCATION        (spec 001 §9)
//  UNRESOLVED-DECISION: AUDIT_CHAIN_HEAD_ANCHOR      (spec 001 §9)
//
//  !!! CEDARPDP-MUST-REFUSE-ENFORCE-WHILE-UNRESOLVED !!!
//  未来 CedarPDP 启动时必须 grep 上述 UNRESOLVED-DECISION 标记;
//  只要还在,enforce 模式一律拒绝启动(只许 shadow)。
//  这是结构性防遗忘:决策没定 = 系统不进 enforce。
//
//  抢跑说明:本文件先于 spec building 阶段创建,且 `agent/` 尚未纳入
//  git。落地前须先 `git add agent/` 否则改动无法追溯。
// ════════════════════════════════════════════════════════════════════


// ─── 红线:forbid 压倒一切 ─────────────────────────────────────────

// [advisory 层] 字符串黑名单。混淆("sub"+"process"、base64)必绕得过;
// 真控制是「低信任 forbid + 强制沙箱(spec 002)」。保留以挡"不费心思"的恶意。
forbid (principal, action == Action::"create_tool", resource)
when {
  resource.source_code like "*subprocess*" ||
  resource.source_code like "*os.system*" ||
  resource.source_code like "*eval(*" ||
  resource.source_code like "*__import__*" ||
  resource.source_code like "*os.remove*" ||
  resource.source_code like "*shutil.rmtree*"
};

// 策略文件 / 审计日志 / 凭证 / git = 不可【变更】红线(防自我提权)
// 覆盖一切变更动作:写 / 删 / 改名 / 改权限 —— 不止 write_file。
// 前提:resource.path 已由 PEP 规范化(解析 .. 与符号链接)后才进 Cedar。
forbid (
  principal,
  action in [Action::"write_file", Action::"delete_file",
             Action::"move_file", Action::"chmod"],
  resource
)
when {
  resource.path like "agent/policies/*" ||
  resource.path like "agent/.audit/*" ||
  resource.path like "*/.env*" ||
  resource.path like "*/.git/*"
};

// 文件变更白名单:除非规范化路径在白名单内,否则拒(写/删/改名)
forbid (
  principal,
  action in [Action::"write_file", Action::"delete_file", Action::"move_file"],
  resource
)
unless {
  resource.path like "data/reports/*" ||
  resource.path like "agent/tools/.tmp/*"
};

// 单轮新建工具上限(防 self-evolving 失控自我增殖)
forbid (principal, action == Action::"create_tool", resource)
when { context.tools_created_this_run >= 2 };

// 低信任来源(抓回的网页内容驱动的动作):禁自我演化/改文件/执行。
// principal 静态,分不清「用户让我」vs「网页让我」;trust 补这个缺口。
forbid (
  principal,
  action in [Action::"create_tool", Action::"write_file",
             Action::"delete_file", Action::"execute_tool"],
  resource
)
when { context.trust == "untrusted" };


// ─── 审批层:允许但需人确认(@gate("approval")) ───────────────────

// registration 本身受控:防止把恶意脚本标记为「已注册」绕执行白名单。
@gate("approval")
permit (
  principal == Agent::"deepinsight",
  action == Action::"register_tool",
  resource
);

@gate("approval")
permit (
  principal == Agent::"deepinsight",
  action == Action::"create_tool",
  resource
);


// ─── 白名单:默认拒绝,显式放行已知操作 ───────────────────────────
// (完成 spec §4.2「显式放行已知」原则:三个 workflow 的声明 step
//  + 已注册工具执行 + 报告/临时目录写入。否则默认拒绝会挡掉正常流程。)

permit (
  principal == Workflow::"daily-radar",
  action in [Action::"fetch_sources", Action::"fetch_hn", Action::"dedup",
             Action::"filter_date", Action::"rank", Action::"summarize",
             Action::"critique", Action::"render"],
  resource
);

permit (
  principal == Workflow::"deep-read",
  action in [Action::"fetch_url", Action::"summarize",
             Action::"critique", Action::"render"],
  resource
);

permit (
  principal == Workflow::"topic-research",
  action in [Action::"search", Action::"dedup", Action::"rank",
             Action::"fetch_url", Action::"summarize",
             Action::"critique", Action::"render"],
  resource
);

// 执行【已注册】工具(resource.registered 必须来自可信 registry,非 agent 输入)
permit (
  principal == Agent::"deepinsight",
  action == Action::"execute_tool",
  resource
)
when { resource.registered == true };

// 报告 / 临时目录写入(规范化路径已由 PEP 处理;红线 forbid 仍优先)
permit (
  principal == Agent::"deepinsight",
  action in [Action::"write_file", Action::"delete_file", Action::"move_file"],
  resource
)
when {
  resource.path like "data/reports/*" ||
  resource.path like "agent/tools/.tmp/*"
};
