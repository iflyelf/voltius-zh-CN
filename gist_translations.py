"""Gist-sync 插件汉化映射表 (SettingsPage.tsx 完整精确映射)"""

GIST_SYNC_TRANSLATIONS = {
    "src/plugins/gist-sync/SettingsPage.tsx": {
        # ─── 顶部标题与说明 ───
        '>GitHub Gist Sync</h2>': '>GitHub Gist 同步</h2>',
        '          Sync your data across devices via encrypted GitHub Gist — no Voltius account required.': '          通过加密的 GitHub Gist 在多设备间同步数据 — 无需 Voltius 账户。',
        '          Data is XChaCha20-Poly1305 encrypted client-side before upload.': '          数据在上传前于客户端使用 XChaCha20-Poly1305 加密。',

        # ─── RolePill / GistRow title 属性 ───
        'title="Read from this gist (import source)"': 'title="从此 gist 读取（导入源）"',
        '"At least one export destination required"': '"至少需要一个导出目标"',
        '"Write to this gist (export destination)"': '"向此 gist 写入（导出目标）"',
        'title="Copy gist URL"': 'title="复制 gist URL"',
        'title="Unlink (keep gist on GitHub)"': 'title="取消关联（保留 GitHub 上的 gist）"',
        'title="Delete gist from GitHub"': 'title="从 GitHub 删除 gist"',

        # ─── setError / toast 消息 ───
        '"Import source gist not found — it may have been deleted."': '"未找到导入源 gist — 它可能已被删除。"',
        '"Gist created and registered"': '"Gist 已创建并注册"',
        '"No Voltius gists found on this account."': '"该账户下未找到 Voltius gist。"',
        '"Gist deleted"': '"Gist 已删除"',
        '`Failed to delete: ${e instanceof Error ? e.message : String(e)}`': '`删除失败：${e instanceof Error ? e.message : String(e)}`',
        '`Removed device: ${device.label}`': '`已移除设备：${device.label}`',
        '`Failed to remove device: ${e instanceof Error ? e.message : String(e)}`': '`移除设备失败：${e instanceof Error ? e.message : String(e)}`',

        # ─── formatRelative 时间格式化 ───
        'return "just now";': 'return "刚刚";',
        '`${Math.floor(diff / 60_000)}m ago`': '`${Math.floor(diff / 60_000)}分钟前`',
        '`${Math.floor(diff / 3_600_000)}h ago`': '`${Math.floor(diff / 3_600_000)}小时前`',

        # ─── Credentials 区块 ───
        '            Credentials\n': '            凭据\n',
        'label="GitHub Personal Access Token"': 'label="GitHub 个人访问令牌"',
        '                Needs <code': '                需要 <code',
        '</code> scope.{" "}': '</code> 权限。{" "}',
        'label="Sync Passphrase"': 'label="同步密码短语"',
        '>— optional</span>': '>— 可选</span>',
        'text="Without a passphrase, data is encrypted using your PAT as the key. If your PAT is compromised, your synced data (including SSH private keys) is also exposed."': 'text="未设置密码短语时，数据将使用您的 PAT 作为密钥加密。如果您的 PAT 泄露，您的同步数据（包括 SSH 私钥）也会暴露。"',
        'placeholder="Leave empty to use PAT-derived encryption…"': 'placeholder="留空则使用基于 PAT 派生的加密…"',
        'hint="Adds an independent encryption layer. Recommended if syncing SSH private keys."': 'hint="添加独立的加密层。如果同步 SSH 私钥则推荐使用。"',

        # ─── Registered Gists 区块 ───
        '              Gists {gists.length': '              Gist 列表 {gists.length',
        '                Toggle <span className="font-medium">Import</span> / <span className="font-medium">Export</span> roles per gist': '                切换每个 gist 的 <span className="font-medium">导入</span> / <span className="font-medium">导出</span> 角色',
        '>No gists registered yet.</p>': '>尚未注册任何 gist。</p>',
        '>Create a new gist or link an existing one below.</p>': '>在下方新建 gist 或关联已有 gist。</p>',

        # ─── 按钮文本 ───
        '                  Creating…': '                  创建中…',
        '                  New Gist': '                  新建 Gist',
        '                  Detecting…': '                  检测中…',
        '                  Auto-detect': '                  自动检测',
        '{showLinkInput ? "Cancel" : "Enter ID manually"}': '{showLinkInput ? "取消" : "手动输入 ID"}',

        # ─── 自动检测结果 ───
        'Found {detectedGists.length} Voltius gist{': '找到 {detectedGists.length} 个 Voltius gist{',
        '? "s" : ""} — select to link:': '? "s" : ""} — 选择以关联：',
        '>linked</span>': '>已关联</span>',
        '\n                        Link\n                      </Btn>': '\n                        关联\n                      </Btn>',

        # ─── 手动输入 ───
        'placeholder="Gist ID or URL (e.g. a1b2c3d4e5f6…)"': 'placeholder="Gist ID 或 URL（例如 a1b2c3d4e5f6…）"',
        '/> : "Link"}': '/> : "关联"}',

        # ─── Sync 区块 ───
        '>\n              Sync\n            </p>': '>\n              同步\n            </p>',
        '<Row label="Status">': '<Row label="状态">',
        '`Synced ${formatRelative(lastSync)}`': '`已同步 ${formatRelative(lastSync)}`',
        '"Not yet synced"': '"尚未同步"',
        '<Row label="Poll interval">': '<Row label="轮询间隔">',
        '>seconds</span>': '>秒</span>',
        '                    Syncing…': '                    同步中…',
        ') : "Sync Now"}': ') : "立即同步"}',

        # ─── Devices 区块 ───
        '              Devices — import source ({sourceManifest.devices.length})': '              设备 — 导入源（{sourceManifest.devices.length}）',
        '(this device)': '（此设备）',
        'last push: {formatRelative(device.pushedAt)}': '最后推送：{formatRelative(device.pushedAt)}',
        '\n                        Remove\n                      </Btn>': '\n                        移除\n                      </Btn>',
    }
}
