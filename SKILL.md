---
name: ssh-audit
description: SSH 审计技能。强制所有 SSH 操作走审计通道，记录 JSONL 日志，内置 14 条高危命令检测规则，支持命令执行、交互式 Shell、会话回放。凭据通过 Windows DPAPI 加密存储。强制输出规范，不可省略任何环节。
---

# SSH 审计技能

## 目的

本技能强制所有 SSH 远程操作走审计通道。AI 执行任何 SSH 命令时，**必须**使用本项目的 CLI 工具或 Python 库，禁止裸 paramiko / subprocess ssh / 其他 SSH 库。所有操作自动记录 JSONL 审计日志、触发规则检测、支持事后回放。

> **强制输出规范（所有 SSH 命令执行后必须完整输出，不可跳过任何一步）：**
> 
> ### 第一步：输出 session 元信息（固定格式）
> ```
> [SSH] session:     <session_id>
> [SSH] target:     <user>@<host>:22
> [SSH] log:        <log_file_path>
> ```
> 
> ### 第二步：输出命令原文（固定格式）
> ```
> ▶ 执行命令: <命令原文>
> ```
> 
> ### 第三步：输出命令解释（固定格式）
> ```
> 【作用】<一句话说明这条命令在做什么>
> ```
> 
> ### 第四步：输出命令输出（原始/raw 输出，完整呈现）
> ```
> ───────────────────────────────
> <命令输出正文，原样呈现>
> ───────────────────────────────
> ```
> 
> ### 第五步：输出执行摘要（固定格式）
> ```
> 【摘要】成功 / 失败（退出码 N） / 异常：<简短说明>
> ```
>
> **⚠️ 禁止行为（违反以下任意一条视为严重违规）：**
> - 跳过 session 元信息输出
> - 跳过命令原文输出（不得只说"查到了"而不展示命令）
> - 跳过命令解释
> - 用自己的话转述命令输出（不得"翻译"或"总结"原始输出，必须原样呈现）
> - 省略命令学习日志写入
> - 在回复中暴露明文密码

---

## 项目路径（环境变量自动发现）

**本技能不硬编码任何绝对路径。** 使用前通过环境变量 `AGENT_SSH_AUDIT_HOME` 定位项目根目录。如果环境变量未设置，按以下优先顺序查找：

1. 环境变量 `AGENT_SSH_AUDIT_HOME`（当前进程）
2. Windows Machine 级别环境变量 `AGENT_SSH_AUDIT_HOME`
3. 兜底：`storage.py` 依赖于自身脚本位置自动推导

---

## 凭据规则

1. 首次使用收到用户名和密码后，**必须询问用户**是否需要将密码加密保存：
   - **询问话术：**「是否需要我帮你将密码加密保存到本地？这样后续使用就无需再次输入密码。如果不需要保存，我会在本次会话中直接使用。」
   - 用户选择**不保存**：本次会话直接使用一次性密码，不写磁盘。
   - 用户选择**保存**：调用 `agent-ssh-cred.py` 通过 Windows DPAPI 加密存储，绑定当前 Windows 用户会话。
2. 禁止在脚本/回复/日志中展示明文密码。Base64 编码可用于传参，不得作为持久化存储。
3. 凭据文件路径：`<AGENT_SSH_AUDIT_HOME>/credentials.txt`（已 DPAPI 加密）。

---

## 命令执行规则

1. 所有 SSH 命令**必须**通过 `SSHAuditClient` 类（`agent_ssh_audit/client.py`）执行。
2. 直接调用 `paramiko` / `subprocess.run(["ssh", ...])` / 其他 SSH 库属于**违规**，触发规则 0 告警。
3. 危险命令（rm -rf /、mkfs、dd 等）命中审计规则时被拦截，并记录违规。
4. 每条命令执行后，将命令展示给用户，并解释其作用。

---

## 审计规则（14 条）

内置 14 条审计规则，覆盖常见高危操作：

| 级别 | 规则 | 触发条件 |
|------|------|---------|
| 🔴 Critical | `rm -rf /` | 递归删除根目录 |
| 🔴 Critical | `rm -rf ~` | 删除家目录 |
| 🟡 Warn | `rm -rf` 绝对路径 | 删除非当前目录下的路径 |
| 🔴 Critical | `dd of=/dev/sd*` | 磁盘直接写入 |
| 🔴 Critical | `mkfs` | 格式化磁盘 |
| 🔴 Critical | `chmod 777 /` | 修改根目录权限 |
| 🔴 Critical | `chown ... /` | 修改根目录属主 |
| 🔴 Critical | `curl url \| bash` | 管道执行远程脚本 |
| 🟡 Warn | `reboot/shutdown/halt` | 重启/关机 |
| 🔴 Critical | `systemctl stop ssh` | 禁用 SSH 服务 |
| 🟡 Warn | `iptables -F` | 清空防火墙规则 |
| 🟡 Warn | `passwd/useradd/userdel` | 用户管理操作 |
| 🔴 Critical | 编辑 `/etc/passwd` 等 | 修改系统配置文件 |
| 🟡 Warn | `history -c` | 清除命令历史 |

---

## 日志规则

### 审计日志（JSONL，已加密）

每条命令写入 `logs/sessions/YYYY-MM-DD.jsonl`，包含时间戳、session_id、命令、结果（加密）、告警状态。文件已加密，不可直接阅读，必须通过 `agent-ssh-replay.py` 解密查看。

```
logs/sessions/YYYY-MM-DD.jsonl
```

### 命令学习日志（Markdown，明文可读）

每次操作后，将执行的命令按天归档到 `logs/cmds_learn/YYYY-MM-DD.md`，便于事后复盘。每条记录包含时间、目标主机、session_id 和命令原文。

```
logs/cmds_learn/YYYY-MM-DD.md
```

---

## 错误处理

1. 连接失败 → 检查网络/端口/防火墙/SSH 服务状态。
2. 认证失败 → 检查用户名/密码是否正确，凭据文件是否损坏。
3. 超时 → 重试一次或提示用户。
4. 权限不足 → 提示用户使用具备权限的账号。

---

## CLI 使用规范

```powershell
# 加密存储密码（首次）
python bin\agent-ssh-cred.py store <服务器IP>

# 单条命令
python bin\agent-ssh-run.py user@host "命令" --show-commands

# 批量命令
python bin\agent-ssh-run.py user@host --batch commands.txt

# 交互式 Shell
python bin\agent-ssh-shell.py user@host

# 会话回放（解密查看审计日志）
python bin\agent-ssh-replay.py logs\sessions\YYYY-MM-DD.jsonl --session <session_id>
```

---

## 会话回放

通过 `agent-ssh-replay.py` 可逐条回放历史命令执行过程，并解密展示命令内容和输出结果。

```powershell
# 查看某日所有 session
python bin\agent-ssh-replay.py logs\sessions\2026-07-11.jsonl

# 指定 session 回放
python bin\agent-ssh-replay.py logs\sessions\2026-07-11.jsonl --session s_001
```

---

## 命令执行后强制输出规范（必须依次输出，缺一不可）

每次 SSH 命令执行完毕，AI **必须**按以下顺序、分段输出，**不得遗漏任何一步**，**不得合并段落**，**不得用自然语言替代**：

### ① Session 元信息（固定格式）
```
[SSH] session:     <session_id>
[SSH] target:     <user>@<host>:22
[SSH] log:        <log_file_path>
```

### ② 命令原文（固定格式）
```
▶ 执行命令: <命令原文>
```

### ③ 命令解释（固定格式）
```
【作用】<一句话说明这条命令在做什么>
```

### ④ 原始输出（raw 原文，原样呈现）
```
───────────────────────────────
<原始命令输出，原封不动>
───────────────────────────────
```

### ⑤ 执行摘要（固定格式）
```
【摘要】成功 / 失败（退出码 N）/ 异常：<一句话说明>
```

> **违规判定：** 缺少任意一节、用自然语言概括原始输出（"我帮你查了一下，这台机器上有..."）、或省略日志写入，均视为违反本 skill，触发规则告警。

---

## 命令学习日志（强制写入，不可省略）

每次 SSH 命令执行完毕后，**立即**将记录追加到 `<AGENT_SSH_AUDIT_HOME>/logs/cmds_learn/YYYY-MM-DD.md`，格式如下：

```markdown
## HH:MM

**用户 @ 主机：** <user> @ <host>

**session_id：** <session_id>

**执行命令：**
```
<命令原文>
```

**用途：**<一句话说明>

---
```

日志为 Markdown 格式，append-only（只追加，不覆盖历史），可直接用 Notepad 打开查看。
