# Codex 版 Agent Factory

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory 是用于人类主导的软件交付的 Codex 插件。它提供范围明确的 Agent
工作流、证据探索和共享项目约定。

## 产品模式

- **仅插件：** 完整的本地工作流。无需 Agent Factory MCP 包、服务器、账户、
  租户、连接或经过身份验证的资源。
- **仅 MCP：** 独立安装的 MCP 应用程序拥有其 Document、Gather、Tool 和
  Workspace 能力，无需此插件。
- **插件与 MCP：** 明确选择并获得授权的连接能力可以扩展本地工作流。它们不会
  接管图权限，也不会隐式传输本地工件。

## 包含的 Skill 和 Agent 模型

此插件恰好公开两个 Skill：

- `agent` 通过托管会话运行 `Main -> Work -> Verification` 图。
- `convention` 负责核心模型和共享项目约定。

Main 与人类沟通、委派范围明确的任务并整合结果。Work 执行任务。Verification
独立检查已完成的 Work，并返回 pass 或 fail，除非人类明确跳过。证据探索是 Work
能力，Interview 是 Main 能力；二者都不会增加 Skill 或角色。

Codex CLI 是默认界面。同一个图也可以通过 `codex exec` 托管，或在 VS Code
扩展程序中呈现。

## 安装

添加由 GitHub 支持的 marketplace 并安装插件：

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin add agent-factory@agent-factory
```

如需安装已发布的更新：

```bash
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

安装或更新后，请启动新的 Codex thread，以便加载 Skill 和工具。插件 manifest
位于 `.codex-plugin/plugin.json`，两个分发的 Skill 位于 `skills/` 下。它们不会
镜像到仓库本地的 `.codex/` 中。

## 兼容性

- **操作系统：** 托管执行支持 Linux。WSL 必须满足 Linux 检查；不支持 macOS
  和原生 Windows。
- **Python：** 源代码级最低版本为 Python 3.10。发布验证覆盖配置的 Python 3.10
  和 3.12 基准。
- **Codex：** 不假定仓库范围的 CLI 版本。运行时预检和已安装能力发现会判断所选
  可执行文件是否就绪。
- **隔离：** 首选使用 cgroup v2 的用户 systemd。私有进程组 fallback 对后代进程的
  隔离能力较弱。

以上是兼容性边界，并不证明特定主机、账户、模型、tier 或 sandbox 已准备就绪。

## 详细文档

持久契约保留在其所属的 Skill 和 reference 中：

- [Agent Skill](skills/agent/SKILL.md)：图角色、委派和执行。
- [Convention Skill](skills/convention/SKILL.md)：共享约定和所有权。
- [核心模型](skills/convention/references/agent-factory-core.md)：角色、能力、权限和产品边界。
- [运行时契约](skills/agent/references/home-runtime.md)：托管会话、路径、receipt、恢复、
  隔离和 migration。
- [目录结构](skills/convention/references/directory-structure.md)：源代码、安装、运行时、
  cloud 和 legacy 布局。
- [Document](skills/convention/references/documents.md)：Document 类型、routing、格式、
  projection 和 synchronization。
- [开发](skills/convention/references/development.md)：更改、Git publication、技术文档和发布准备。
- [测试](skills/convention/references/testing.md)：测试组织和验证边界。
- [Native Fast 和 Goal](skills/agent/references/native-fast-goal.md) 以及
  [项目专用 Work](skills/agent/references/project-specialist.md)：可选执行指南和专用化设计。

## 状态

欢迎提供反馈和 Issue 报告。

## 许可证

MIT License。请参阅 [LICENSE](LICENSE)。
