// ════════════════════════════════════════════════════════════════════
//  agent.cedar — DeepInsight Cedar 策略闸门 (spec 001)
//  status: Phase 0 — 由 CedarPDP 加载;每条策略带 @id 供审计/三态映射
// --------------------------------------------------------------------
//  ✅ DECISIONS-LOCKED 2026-05-15(详见同目录 DECISIONS-REQUIRED.md):
//    ① TRUST_ANCHOR        = Git(PDP 比对工作区本文件与 HEAD blob;
//                            运行中本文件被改/删 → deny-all-dangerous)
//    ② AUDIT_CHAIN_HEAD    = stderr(每次决策链头 hash 打到 stderr,
//                            harness/终端捕获,子进程改不了已 flush 的)
//
//  三态:带 @gate("approval") 的 permit 命中 → REQUIRE_APPROVAL。
//  评估顺序由 Cedar 保证:任一 forbid 命中即 DENY;否则 permit;否则默认拒绝。
//  抢跑说明:`agent/` 已纳入 git(2026-05-15);本文件为权威策略源。
// ════════════════════════════════════════════════════════════════════


// ─── 红线:forbid 压倒一切 ─────────────────────────────────────────

// [advisory] 字符串黑名单。混淆("sub"+"process"、base64)必绕得过;
// 真控制是「低信任 forbid + 强制沙箱(spec 002)」。保留挡"不费心思"的恶意。
@id("forbid.dangerous_module")
forbid (principal, action == Action::"create_tool", resource)
when {
  resource.source_code like "*subprocess*" ||
  resource.source_code like "*os.system*" ||
  resource.source_code like "*eval(*" ||
  resource.source_code like "*__import__*" ||
  resource.source_code like "*os.remove*" ||
  resource.source_code like "*shutil.rmtree*"
};

// 策略 / 审计 / 凭证 / git = 不可【变更】红线(防自我提权)
// 覆盖写/删/改名/改权限;resource.path 已由 PEP 规范化后才进 Cedar。
@id("forbid.policy_secret_mutate")
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
@id("forbid.write_outside_whitelist")
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
@id("forbid.tool_cap")
forbid (principal, action == Action::"create_tool", resource)
when { context.tools_created_this_run >= 2 };

// 低信任来源(抓回网页内容驱动):禁自我演化/改文件/执行。
@id("forbid.untrusted_context")
forbid (
  principal,
  action in [Action::"create_tool", Action::"write_file",
             Action::"delete_file", Action::"execute_tool"],
  resource
)
when { context.trust == "untrusted" };


// ─── 审批层:允许但需人确认(@gate("approval")) ───────────────────

@id("approve.register_tool")
@gate("approval")
permit (
  principal == Agent::"deepinsight",
  action == Action::"register_tool",
  resource
);

@id("approve.create_tool")
@gate("approval")
permit (
  principal == Agent::"deepinsight",
  action == Action::"create_tool",
  resource
);


// ─── 白名单:默认拒绝,显式放行已知操作 ───────────────────────────

@id("permit.workflow.daily_radar")
permit (
  principal == Workflow::"daily-radar",
  action in [Action::"fetch_sources", Action::"fetch_hn", Action::"dedup",
             Action::"filter_date", Action::"rank", Action::"summarize",
             Action::"critique", Action::"render"],
  resource
);

@id("permit.workflow.deep_read")
permit (
  principal == Workflow::"deep-read",
  action in [Action::"fetch_url", Action::"summarize",
             Action::"critique", Action::"render"],
  resource
);

@id("permit.workflow.topic_research")
permit (
  principal == Workflow::"topic-research",
  action in [Action::"search", Action::"dedup", Action::"rank",
             Action::"fetch_url", Action::"summarize",
             Action::"critique", Action::"render"],
  resource
);

@id("permit.execute_registered_tool")
permit (
  principal == Agent::"deepinsight",
  action == Action::"execute_tool",
  resource
)
when { resource.registered == true };

@id("permit.report_write")
permit (
  principal == Agent::"deepinsight",
  action in [Action::"write_file", Action::"delete_file", Action::"move_file"],
  resource
)
when {
  resource.path like "data/reports/*" ||
  resource.path like "agent/tools/.tmp/*"
};
