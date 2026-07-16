"""插件元数据(index.ts)和逻辑文件(sync-engine/updateActions/useProxmox)汉化映射表。"""

PLUGIN_META_TRANSLATIONS = {
    "src/plugins/monitoring/index.ts": {
        'name: "System Metrics"': 'name: "系统指标"',
        'description: "Real-time CPU, RAM, network, and disk metrics for local and SSH sessions."':
            'description: "面向本地和 SSH 会话的实时 CPU、RAM、网络和磁盘指标。"',
        'label: "Metrics"': 'label: "指标"',
    },
    "src/plugins/process-manager/index.ts": {
        'name: "Process Manager"': 'name: "进程管理器"',
        'description: "Monitor and manage running processes for local and SSH sessions."':
            'description: "监控和管理本地和 SSH 会话的运行进程。"',
        'label: "Processes"': 'label: "进程"',
    },
    "src/plugins/proxmox/index.ts": {
        'name: "Proxmox LXC"': 'name: "Proxmox 容器"',
        'description: "Manage Proxmox VE LXC containers and snapshots over SSH."':
            'description: "通过 SSH 管理 Proxmox VE LXC 容器和快照。"',
        'label: "Proxmox LXC"': 'label: "Proxmox 容器"',
    },
    "src/plugins/docker/index.ts": {
        'description: "Manage Docker containers, images, volumes, and networks for local and SSH sessions."':
            'description: "管理本地和 SSH 会话的 Docker 容器、镜像、卷和网络。"',
        'label: "Automatic update checks"': 'label: "自动检查更新"',
        '"Check images against their registries when the Images view opens. A manual \u201ccheck updates\u201d button is always available regardless of this setting."':
            '"打开镜像视图时对照镜像仓库检查镜像。无论此设置如何，手动\u201c检查更新\u201d按钮始终可用。"',
        'label: "Re-check interval (hours)"': 'label: "重新检查间隔（小时）"',
        '"Cached results are reused within this window to avoid registry rate limits. Resolving registry digests uses docker buildx; hosts without it show images as \u201cunknown\u201d rather than reporting a false update."':
            '"在此时间窗口内复用缓存结果，以避免触发镜像仓库的速率限制。解析镜像仓库摘要使用 docker buildx；不支持它的主机会将镜像显示为\u201cunknown\u201d，而不是报告错误的更新。"',
        'label: "Recreate containers after pulling"': 'label: "拉取后重建容器"',
        '"After pulling an update, recreate the containers using that image so they actually run the new version. Compose services are recreated via compose; standalone containers are rebuilt from their docker run config. When off, the image is only pulled."':
            '"拉取更新后，使用该镜像重建容器，使其实际运行新版本。Compose 服务通过 compose 重建；独立容器则根据其 docker run 配置重建。关闭时仅拉取镜像。"',
    },
    "src/plugins/gist-sync/index.ts": {
        'name: "GitHub Gist Sync"': 'name: "GitHub Gist 同步"',
        '"Sync your data across devices via encrypted GitHub Gist — no Voltius account required."':
            '"通过加密的 GitHub Gist 在设备间同步数据 — 无需 Voltius 账户。"',
        'label: "GitHub Gist Sync"': 'label: "GitHub Gist 同步"',
    },
    "src/plugins/ssh-config/index.ts": {
        'name: "SSH Config Sync"': 'name: "SSH 配置同步"',
        "description: \"Auto-syncs hosts from ~/.ssh/config. Connections are tagged 'ssh-config'.\"":
            "description: \"自动从 ~/.ssh/config 同步主机。连接会被标记为 'ssh-config'。\"",
        '`SSH key imported: ${name}`': '`SSH 密钥已导入: ${name}`',
        '`SSH identity created: ${host.alias}`': '`SSH 身份已创建: ${host.alias}`',
        '`SSH host added: ${host.alias}`': '`SSH 主机已添加: ${host.alias}`',
        'label: "SSH Config Sync"': 'label: "SSH 配置同步"',
        '"Sync"': '"同步"',
        '"Poll interval"': '"轮询间隔"',
        '"How often to check ~/.ssh/config for changes"':
            '"检查 ~/.ssh/config 变更的频率"',
        '"seconds"': '"秒"',
        'syncing ? "Syncing…" : "Sync now"': 'syncing ? "同步中…" : "立即同步"',
        '"Notifications"': '"通知"',
        '"Show a toast when hosts, keys, or identities are created"':
            '"创建主机、密钥或身份时显示提示"',
    },
    "src/plugins/gist-sync/sync-engine.ts": {
        '"Unknown device"': '"未知设备"',
        '_api.notifications.progress("Syncing via GitHub Gist…", { indeterminate: true })':
            '_api.notifications.progress("正在通过 GitHub Gist 同步…", { indeterminate: true })',
        'progress.finish("Gist sync complete")': 'progress.finish("Gist 同步完成")',
        '_api.notifications.toast("Gist sync complete", { severity: "success" })':
            '_api.notifications.toast("Gist 同步完成", { severity: "success" })',
        'progress.error("Gist sync failed")': 'progress.error("Gist 同步失败")',
        'setGistState("error", "GitHub PAT is invalid or expired")':
            'setGistState("error", "GitHub PAT 无效或已过期")',
        '"Gist Sync: GitHub PAT is invalid or expired"':
            '"Gist 同步: GitHub PAT 无效或已过期"',
        'setGistState("error", "Gist not found — re-configure in Settings")':
            'setGistState("error", "未找到 Gist — 请在设置中重新配置")',
        '"Gist Sync: Gist not found — re-configure in Settings"':
            '"Gist 同步: 未找到 Gist — 请在设置中重新配置"',
        '`Gist Sync: repeated failures — ${msg}`':
            '`Gist 同步: 多次失败 — ${msg}`',
        '_api.notifications.toast("Gist sync skipped — offline?", { severity: "warning" })':
            '_api.notifications.toast("已跳过 Gist 同步 — 是否离线？", { severity: "warning" })',
    },
    "src/plugins/docker/updateActions.ts": {
        '`Pulled ${image}`': '`已拉取 ${image}`',
        '`recreated ${r.recreated.length}`': '`已重建 ${r.recreated.length} 个`',
        '`${r.manual.length} need manual recreation`':
            '`${r.manual.length} 个需要手动重建`',
        'parts.push("no running containers")': 'parts.push("无运行中的容器")',
        '`${image} is already up to date`': '`${image} 已是最新`',
        '`${image}: no new image pulled${detail}`': '`${image}: 未拉取到新镜像${detail}`',
    },
    "src/plugins/proxmox/useProxmox.ts": {
        '`Shell failed: ${e}`': '`Shell 失败: ${e}`',
    },
}
