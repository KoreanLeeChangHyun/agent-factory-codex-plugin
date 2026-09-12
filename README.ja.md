# Codex 向け Agent Factory

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> このプラグインは活発に開発中です。Skill、成果物形式、ワークフローは
> 予告なく変更される場合があります。

Agent Factory は、人間の指示に基づくソフトウェアデリバリーのための Codex
プラグインです。範囲を限定した Agent ワークフロー、根拠探索、共通の
プロジェクト規約を提供します。

## 製品モード

- **プラグインのみ:** 完全なローカルワークフローです。Agent Factory MCP
  パッケージ、サーバー、アカウント、テナント、接続、認証済みリソースは不要です。
- **MCP のみ:** 独立してインストールされた MCP アプリケーションが、この
  プラグインなしで自身の Document、Gather、Tool、Workspace 機能を所有します。
- **プラグインと MCP:** 明示的に選択および承認された接続機能でローカル
  ワークフローを拡張できます。グラフの権限を引き継いだり、ローカルの
  成果物を暗黙に送信したりすることはありません。

## 収録 Skill と Agent モデル

このプラグインが公開する Skill は、正確に次の 2 つです。

- `agent` は管理対象セッションで `Main -> Work -> Verification` グラフを実行します。
- `convention` はコアモデルと共通のプロジェクト規約を所有します。

Main は人間と対話し、範囲を限定したタスクを委任して結果を統合します。Work は
タスクを実行します。Verification は完了した Work を独立して確認し、人間が明示的に
省略しない限り pass または fail を返します。根拠探索は Work の機能、Interview は
Main の機能であり、どちらも Skill や役割を追加するものではありません。

Codex CLI がデフォルトのインターフェースです。同じグラフを `codex exec` で
ホストしたり、VS Code 拡張機能から表示したりすることもできます。

## インストール

GitHub を参照する marketplace を追加し、プラグインをインストールします。

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin add agent-factory@agent-factory
```

公開済みの更新をインストールするには、次を実行します。

```bash
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

インストールまたは更新後、新しい Codex thread を開始して Skill とツールを
読み込んでください。プラグイン manifest は `.codex-plugin/plugin.json`、配布される
2 つの Skill は `skills/` 以下にあります。リポジトリ内の `.codex/` には複製されません。

## 互換性

- **オペレーティングシステム:** 管理対象実行は Linux をサポートします。WSL は
  Linux のチェックを満たす必要があり、macOS とネイティブ Windows は非対応です。
- **Python:** ソースレベルの最低バージョンは Python 3.10 です。リリース検証は、
  構成された Python 3.10 および 3.12 のベースラインを対象とします。
- **Codex:** リポジトリ全体に適用する CLI バージョンは仮定しません。ランタイムの
  事前確認とインストール済み機能の検出により、選択した実行ファイルの準備状況を判断します。
- **封じ込め:** cgroup v2 を使用するユーザー systemd が推奨されます。非公開の
  プロセスグループ fallback は、子孫プロセスの封じ込めが弱くなります。

これらは互換性の境界であり、特定のホスト、アカウント、モデル、tier、sandbox の
準備が整っていることを証明するものではありません。

## 詳細ドキュメント

永続的な契約は、それを所有する Skill と reference に保持されています。

- [Agent Skill](skills/agent/SKILL.md): グラフの役割、委任、実行。
- [Convention Skill](skills/convention/SKILL.md): 共通規約と所有権。
- [コアモデル](skills/convention/references/agent-factory-core.md): 役割、機能、権限、製品境界。
- [ランタイム契約](skills/agent/references/home-runtime.md): 管理対象セッション、パス、
  receipt、復旧、封じ込め、migration。
- [ディレクトリ構造](skills/convention/references/directory-structure.md): ソース、
  インストール、ランタイム、cloud、legacy のレイアウト。
- [Document](skills/convention/references/documents.md): Document の種類、routing、
  形式、projection、synchronization。
- [開発](skills/convention/references/development.md): 変更、Git publication、
  技術ドキュメント、リリース準備。
- [テスト](skills/convention/references/testing.md): テスト構成と検証境界。
- [Native Fast と Goal](skills/agent/references/native-fast-goal.md) および
  [プロジェクト特化 Work](skills/agent/references/project-specialist.md):
  オプションの実行指針と特化設計。

## ステータス

Alpha です。フィードバックや Issue 報告を歓迎しますが、現時点では本番環境との
互換性を保証していません。

## ライセンス

MIT License です。[LICENSE](LICENSE) を参照してください。
