/**
 * UI strings in Japanese and English.
 *
 * The backend sends stable codes (lint issues, doctor findings, manager
 * errors) rather than display text, so everything the user reads is
 * translated here. Static markup is tagged with data-i18n / -placeholder /
 * -title attributes and filled in by applyI18n().
 */
window.I18N = (() => {
  const STRINGS = {
    ja: {
      "nav.target": "有効化先",
      "nav.manageTargets": "有効化先を追加・削除",
      "nav.profile": "プロファイル",
      "nav.profile.pick": "（選択）",
      "nav.apply": "適用",
      "nav.saveCurrent": "現状を保存",
      "nav.saveCurrent.title": "現在の有効化状態をプロファイルとして保存",
      "nav.delete": "削除",
      "nav.language": "言語",

      "bar.newSkill": "＋ 新規スキル",
      "bar.icons": "アイコン設定",
      "bar.doctor": "診断",
      "bar.doctorFound": "診断: 要対応 {count}件",
      "bar.stats": "{path} — スキル {total}件 / 有効化 {enabled}件",
      "bar.tokens": "常時コンテキスト 約{tokens}トークン（説明 {chars}文字）",
      "bar.tokens.title": "有効化中スキルの name + description は常にコンテキストに載ります（概算）",

      "sources.title": "スキルソース",
      "sources.rescan": "再スキャン",
      "sources.empty": "まだソースが登録されていません。",
      "sources.path.placeholder": "~/repos/my-skills/skills など、絶対パスか ~ 展開可",
      "sources.label.placeholder": "ラベル（省略可）",
      "sources.add": "ソースを追加",
      "sources.missing": "(パスが見つかりません)",
      "sources.remove": "削除",
      "sources.removeConfirm": "ソース「{label}」の登録を解除しますか？\n(スキャン対象から外れるだけで、既に有効化中のスキルはそのまま残ります)",
      "sources.addFailed": "ソースの追加に失敗しました: {message}",

      "filter.search": "名前・説明で検索...",
      "filter.fullText": "本文も検索",
      "filter.allCategories": "すべてのカテゴリ",
      "filter.allSources": "すべてのソース",
      "filter.issuesOnly": "要確認のみ",
      "filter.enabledOnly": "有効化済みのみ",
      "filter.noMatch": "条件に一致するスキルがありません。",
      "empty.state": "スキルが見つかりません。上でソースを追加してください。",

      "card.enabled": "有効 ({name})",
      "card.enabled.copy": "有効 ({name} / コピー)",
      "card.disabled": "無効",
      "card.edit": "編集",
      "card.select.title": "エクスポート/プロファイル対象に選択",
      "card.tokens": "約{tokens}tok",
      "card.tokens.title": "有効化した場合の常時コスト（概算）",
      "category.count": "({count})",
      "category.countEnabled": "({count} / 有効分 約{tokens}tok)",

      "toggle.conflict": "名前が衝突しました:\n{message}\n\n別の名前で有効化しますか？（空でキャンセル）",
      "toggle.enableFailed": "有効化に失敗しました: {message}",
      "toggle.disableConfirm": "「{name}」を無効化しますか？\n{path} から削除されます（元のソースファイルは削除されません）。",
      "toggle.disableFailed": "無効化に失敗しました: {message}",

      "export.selected": "{count} 件選択中",
      "export.selectedTokens": "（有効化すると常時 約{tokens}トークン）",
      "export.run": "選択したスキルをエクスポート",
      "export.toProfile": "選択からプロファイル作成",
      "export.clear": "選択解除",
      "export.failed": "エクスポートに失敗しました",

      "profile.pickFirst": "プロファイルを選択してください。",
      "profile.applyConfirm": "プロファイル「{name}」を {path} に適用します。\nこのプロファイルに含まれないスキルは無効化されます（手動配置のスキルは対象外）。",
      "profile.applyResult": "有効化: {enabled}件 / 無効化: {disabled}件",
      "profile.applyErrors": "エラー:\n{errors}",
      "profile.namePrompt": "プロファイル名",
      "profile.deleteConfirm": "プロファイル「{name}」を削除しますか？（有効化状態は変わりません）",
      "profile.option": "{name} — {count}件 / 約{tokens}tok",
      "profile.optionMissing": "{name} — {count}件 / 約{tokens}tok / 不明{missing}",

      "targets.title": "有効化先（ターゲット）",
      "targets.help": "ユーザーグローバル（<code>~/.claude/skills</code>）に加えて、プロジェクトごとの <code>&lt;project&gt;/.claude/skills</code> を有効化先として登録できます。プロジェクトのルートを入力すれば <code>.claude/skills</code> を補完します。",
      "targets.global": "ユーザーグローバル",
      "targets.builtin": "既定",
      "targets.notCreated": "(未作成)",
      "targets.path.placeholder": "~/repos/my-project",
      "targets.label.placeholder": "ラベル（省略可）",
      "targets.add": "追加",
      "targets.removeConfirm": "この有効化先の登録を解除しますか？\n（登録が外れるだけで、既に作成済みのリンクは残ります）",
      "targets.addFailed": "有効化先の追加に失敗しました: {message}",

      "edit.title": "スキルを編集",
      "edit.tab.skill": "SKILL.md",
      "edit.tab.files": "同梱ファイル",
      "edit.name": "name",
      "edit.description": "description",
      "edit.descCounter": "{length} / 1024 文字",
      "edit.body": "本文（Markdown）",
      "edit.filePlaceholder": "左のファイルを選択すると内容を表示します。",
      "edit.fileBinary": "（バイナリのため表示できません）",
      "edit.fileTooLarge": "（サイズ超過のため表示できません）",
      "edit.duplicate": "複製",
      "edit.close": "閉じる",
      "edit.save": "保存（自動バックアップ）",
      "edit.saved": "保存しました。バックアップ: {path}",
      "edit.nameRequired": "name は必須です",
      "edit.saveFailed": "保存に失敗しました: {message}",
      "edit.duplicatePrompt": "複製後の名前（フォルダ名になります）",
      "edit.duplicated": "複製しました: {name}",
      "edit.duplicateFailed": "複製に失敗しました: {message}",

      "new.title": "新規スキルを作成",
      "new.source": "作成先ソース",
      "new.category": "カテゴリ（フォルダ。空なら直下）",
      "new.description.placeholder": "何をするスキルか＋いつ使うか",
      "new.create": "作成",
      "new.required": "ソースと name は必須です",
      "new.failed": "作成に失敗しました: {message}",

      "doctor.title": "診断",
      "doctor.clean": "問題は見つかりませんでした。",
      "doctor.relink": "再リンク",
      "doctor.forget": "管理から外す",
      "doctor.repairFailed": "修復に失敗しました: {message}",
      "doctor.link_missing": "有効化したはずのエントリが実際には存在しません（手動削除された可能性）。",
      "doctor.source_missing": "リンク先のソースフォルダが存在しません。",
      "doctor.copy_stale": "コピー方式のため、ソース側の更新が反映されていません。",
      "doctor.source_unregistered": "有効化中ですが、現在登録中のソースからは見つかりません。",
      "doctor.external": "skill-launcher の管理外エントリです（手動配置。変更しません）。",

      "icons.title": "カテゴリのアイコン",
      "icons.help": "カテゴリ名 → 絵文字。空欄にすると既定に戻ります（SKILL.md の <code>icon:</code> が最優先）。",
      "icons.save": "保存",

      "lint.no_frontmatter": "YAMLフロントマター（--- で囲まれたブロック）がありません。",
      "lint.name_missing": "frontmatter に name がありません。",
      "lint.name_too_long": "name が長すぎます（{length} 文字 / 上限 {max} 文字）。",
      "lint.name_not_kebab": "name は英小文字・数字・ハイフンのみ（例: my-skill）が推奨です。",
      "lint.name_folder_mismatch": "name「{name}」がフォルダ名「{dir_name}」と一致しません。",
      "lint.description_missing": "description がありません。Claude はこれを見て起動判断をします。",
      "lint.description_too_long": "description が長すぎます（{length} 文字 / 上限 {max} 文字）。",
      "lint.description_too_short": "description が短すぎます。何をするか＋いつ使うかを書くと起動精度が上がります。",
      "lint.body_empty": "本文が空です。手順や参照情報が無いとスキルとして機能しません。",
      "lint.unknown_keys": "見慣れない frontmatter キー: {keys}",
    },

    en: {
      "nav.target": "Activate into",
      "nav.manageTargets": "Add or remove activation targets",
      "nav.profile": "Profile",
      "nav.profile.pick": "(pick one)",
      "nav.apply": "Apply",
      "nav.saveCurrent": "Save current",
      "nav.saveCurrent.title": "Save the current activation set as a profile",
      "nav.delete": "Delete",
      "nav.language": "Language",

      "bar.newSkill": "＋ New skill",
      "bar.icons": "Icons",
      "bar.doctor": "Doctor",
      "bar.doctorFound": "Doctor: {count} to fix",
      "bar.stats": "{path} — {total} skills / {enabled} enabled",
      "bar.tokens": "Always-on context ≈{tokens} tokens ({chars} chars of description)",
      "bar.tokens.title": "Every enabled skill keeps its name + description in the system prompt (estimate)",

      "sources.title": "Skill sources",
      "sources.rescan": "Rescan",
      "sources.empty": "No sources registered yet.",
      "sources.path.placeholder": "~/repos/my-skills/skills — absolute path or ~",
      "sources.label.placeholder": "Label (optional)",
      "sources.add": "Add source",
      "sources.missing": "(path not found)",
      "sources.remove": "Remove",
      "sources.removeConfirm": "Unregister the source \"{label}\"?\n(It just stops being scanned; skills already enabled stay enabled.)",
      "sources.addFailed": "Could not add the source: {message}",

      "filter.search": "Search name and description...",
      "filter.fullText": "Search bodies too",
      "filter.allCategories": "All categories",
      "filter.allSources": "All sources",
      "filter.issuesOnly": "Needs attention",
      "filter.enabledOnly": "Enabled only",
      "filter.noMatch": "No skill matches these filters.",
      "empty.state": "No skills found. Add a source above.",

      "card.enabled": "enabled ({name})",
      "card.enabled.copy": "enabled ({name} / copy)",
      "card.disabled": "disabled",
      "card.edit": "Edit",
      "card.select.title": "Select for export / profile",
      "card.tokens": "≈{tokens} tok",
      "card.tokens.title": "Always-on cost once enabled (estimate)",
      "category.count": "({count})",
      "category.countEnabled": "({count} / ≈{tokens} tok enabled)",

      "toggle.conflict": "Name conflict:\n{message}\n\nEnable it under a different name? (empty to cancel)",
      "toggle.enableFailed": "Could not enable: {message}",
      "toggle.disableConfirm": "Disable \"{name}\"?\nIt will be removed from {path} (the source files are kept).",
      "toggle.disableFailed": "Could not disable: {message}",

      "export.selected": "{count} selected",
      "export.selectedTokens": "(≈{tokens} tokens always-on if enabled)",
      "export.run": "Export selected skills",
      "export.toProfile": "Save selection as profile",
      "export.clear": "Clear selection",
      "export.failed": "Export failed",

      "profile.pickFirst": "Pick a profile first.",
      "profile.applyConfirm": "Apply the profile \"{name}\" to {path}.\nSkills not in the profile will be disabled (hand-placed skills are never touched).",
      "profile.applyResult": "Enabled: {enabled} / Disabled: {disabled}",
      "profile.applyErrors": "Errors:\n{errors}",
      "profile.namePrompt": "Profile name",
      "profile.deleteConfirm": "Delete the profile \"{name}\"? (Nothing is activated or deactivated.)",
      "profile.option": "{name} — {count} skills / ≈{tokens} tok",
      "profile.optionMissing": "{name} — {count} skills / ≈{tokens} tok / {missing} missing",

      "targets.title": "Activation targets",
      "targets.help": "Besides the user-global <code>~/.claude/skills</code>, you can register a project's <code>&lt;project&gt;/.claude/skills</code>. Enter the project root and <code>.claude/skills</code> is filled in for you.",
      "targets.global": "User global",
      "targets.builtin": "default",
      "targets.notCreated": "(not created yet)",
      "targets.path.placeholder": "~/repos/my-project",
      "targets.label.placeholder": "Label (optional)",
      "targets.add": "Add",
      "targets.removeConfirm": "Unregister this activation target?\n(Only the registration goes away; links already created stay.)",
      "targets.addFailed": "Could not add the target: {message}",

      "edit.title": "Edit skill",
      "edit.tab.skill": "SKILL.md",
      "edit.tab.files": "Bundled files",
      "edit.name": "name",
      "edit.description": "description",
      "edit.descCounter": "{length} / 1024 chars",
      "edit.body": "Body (Markdown)",
      "edit.filePlaceholder": "Pick a file on the left to see its contents.",
      "edit.fileBinary": "(binary file — not shown)",
      "edit.fileTooLarge": "(too large to show)",
      "edit.duplicate": "Duplicate",
      "edit.close": "Close",
      "edit.save": "Save (backed up first)",
      "edit.saved": "Saved. Backup: {path}",
      "edit.nameRequired": "name is required",
      "edit.saveFailed": "Could not save: {message}",
      "edit.duplicatePrompt": "Name for the copy (this becomes the folder name)",
      "edit.duplicated": "Duplicated: {name}",
      "edit.duplicateFailed": "Could not duplicate: {message}",

      "new.title": "Create a new skill",
      "new.source": "Create in source",
      "new.category": "Category (folder; empty = source root)",
      "new.description.placeholder": "What it does, and when to use it",
      "new.create": "Create",
      "new.required": "source and name are required",
      "new.failed": "Could not create: {message}",

      "doctor.title": "Doctor",
      "doctor.clean": "No problems found.",
      "doctor.relink": "Relink",
      "doctor.forget": "Stop managing",
      "doctor.repairFailed": "Repair failed: {message}",
      "doctor.link_missing": "This entry is recorded as enabled but does not exist (deleted by hand?).",
      "doctor.source_missing": "The source folder this entry points at is gone.",
      "doctor.copy_stale": "Activated as a copy, and the source has changed since.",
      "doctor.source_unregistered": "Enabled, but not found in any currently registered source.",
      "doctor.external": "Not managed by skill-launcher (placed by hand; left untouched).",

      "icons.title": "Category icons",
      "icons.help": "Category name → emoji. Leave empty for the default (a skill's own <code>icon:</code> always wins).",
      "icons.save": "Save",

      "lint.no_frontmatter": "No YAML frontmatter (the block fenced by ---).",
      "lint.name_missing": "No name in the frontmatter.",
      "lint.name_too_long": "name is too long ({length} chars / max {max}).",
      "lint.name_not_kebab": "name should use lowercase letters, digits and hyphens only (e.g. my-skill).",
      "lint.name_folder_mismatch": "name \"{name}\" does not match the folder name \"{dir_name}\".",
      "lint.description_missing": "No description. Claude decides whether to load the skill from this field.",
      "lint.description_too_long": "description is too long ({length} chars / max {max}).",
      "lint.description_too_short": "description is very short. Say what it does and when to use it.",
      "lint.body_empty": "The body is empty. Without steps or references the skill does nothing.",
      "lint.unknown_keys": "Unrecognised frontmatter keys: {keys}",
    },
  };

  const LS_LANG = "skill-launcher.lang";

  function detect() {
    const saved = localStorage.getItem(LS_LANG);
    if (saved && STRINGS[saved]) return saved;
    return (navigator.language || "en").toLowerCase().startsWith("ja") ? "ja" : "en";
  }

  let lang = detect();

  function t(key, params) {
    const table = STRINGS[lang] || STRINGS.en;
    let s = table[key] ?? STRINGS.en[key] ?? key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        s = s.replaceAll(`{${k}}`, String(v));
      }
    }
    return s;
  }

  function setLang(next) {
    if (!STRINGS[next]) return;
    lang = next;
    localStorage.setItem(LS_LANG, next);
    document.documentElement.lang = next;
  }

  /** Fill every element tagged with data-i18n* from the current table. */
  function applyStatic(root = document) {
    root.querySelectorAll("[data-i18n]").forEach(node => {
      node.textContent = t(node.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-html]").forEach(node => {
      node.innerHTML = t(node.dataset.i18nHtml);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach(node => {
      node.placeholder = t(node.dataset.i18nPlaceholder);
    });
    root.querySelectorAll("[data-i18n-title]").forEach(node => {
      node.title = t(node.dataset.i18nTitle);
    });
    document.documentElement.lang = lang;
  }

  return { t, setLang, applyStatic, get lang() { return lang; } };
})();
