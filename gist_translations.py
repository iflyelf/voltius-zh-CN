"""Gist-sync 插件汉化映射表"""

GIST_SYNC_TRANSLATIONS = {
    "src/plugins/gist-sync/SettingsPage.tsx": {
        # ─── 删除确认对话框 ──────────────────────────────────────────
        'Permanently delete <span className="font-mono">{shortId}</span> from GitHub?':
            '永久从 GitHub 删除 <span className="font-mono">{shortId}</span>？',
        '\n            Cancel\n': '\n            取消\n',
        '\n                Deleting…\n': '\n                删除中…\n',
        ') : "Delete"}': ') : "删除"}',
        
        # ─── Gist 行操作 ──────────────────────────────────────────
        'title="Open on GitHub"': 'title="在 GitHub 打开"',
        'label="Import"': 'label="导入"',
        'label="Export"': 'label="导出"',
        'title="Copy Gist ID"': 'title="复制 Gist ID"',
        'title="Delete Gist from GitHub (destructive)"': 'title="从 GitHub 删除 Gist（危险操作）"',
        
        # ─── Gist 创建表单 ──────────────────────────────────────────
        'placeholder="Snapshot name"': 'placeholder="快照名称"',
        '\n        Create new Gist\n': '\n        创建新 Gist\n',
        '\n        Cancel\n': '\n        取消\n',
        '\n            Creating…\n': '\n            创建中…\n',
        ') : "Create"}': ') : "创建"}',
        
        # ─── 空状态 ──────────────────────────────────────────
        '>No gists registered yet<': '>尚未注册任何 gist<',
        '>Create your first Gist snapshot<': '>创建您的第一个 Gist 快照<',
        'Enter your GitHub PAT above, then click': '在上方输入您的 GitHub PAT，然后点击',
        
        # ─── PAT 输入表单 ──────────────────────────────────────────
        'placeholder="ghp_xxxx…"': 'placeholder="ghp_xxxx…"',
        '\n          Remove\n': '\n          移除\n',
        '"PAT removed"': '"PAT 已移除"',
        '\n          Save\n': '\n          保存\n',
        '\n            Saving…\n': '\n            保存中…\n',
        ') : "Save"}': ') : "保存"}',
        '"PAT saved"': '"PAT 已保存"',
        '"Enter your GitHub PAT first."': '"请先输入您的 GitHub PAT。"',
        
        # ─── 同步密码表单 ──────────────────────────────────────────
        'placeholder="••••••••"': 'placeholder="••••••••"',
        '\n          Unlink\n': '\n          取消关联\n',
        '"Unlinked"': '"已取消关联"',
        '\n          Link\n': '\n          关联\n',
        '\n            Linking…\n': '\n            关联中…\n',
        ') : "Link"}': ') : "关联"}',
        '"Gist linked"': '"Gist 已关联"',
        '"Enter a sync passphrase first."': '"请先输入同步密码。"',
        
        # ─── 轮询间隔表单 ──────────────────────────────────────────
        '\n          Sync\n': '\n          同步\n',
        '\n            Syncing…\n': '\n            同步中…\n',
        ') : "Sync"}': ') : "同步"}',
        '"Synced"': '"已同步"',
        '"Sync failed"': '"同步失败"',
    }
}
