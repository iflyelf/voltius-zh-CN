"""插件汉化映射表 (plugins 目录未接入 i18n,通过精确字符串替换汉化)。

结构: { 相对文件路径: { 原文片段: 替换片段, ... } }
路径相对于 voltius 仓库根目录。
"""

PLUGIN_TRANSLATIONS = {
    # ═══════════════════════════ Docker ═══════════════════════════
    "src/plugins/docker/components/UpdateBadge.tsx": {
        'title="A newer image is available in the registry"': 'title="registry 中有更新的镜像可用"',
        '>\n        update\n      </span>': '>\n        更新\n      </span>',
        'title="Up to date"': 'title="已是最新"',
        '`Could not check: ${status.error}`': '`无法检查: ${status.error}`',
        '"Update status unknown"': '"更新状态未知"',
    },
    "src/plugins/docker/components/VolumeList.tsx": {
        '{volumes.length} volumes': '{volumes.length} 数据卷',
        '{pruning ? "pruning…" : "prune"}': '{pruning ? "清理中…" : "清理"}',
        '>No volumes<': '>无数据卷<',
        'title="Remove volume"': 'title="移除数据卷"',
    },
    "src/plugins/docker/components/NetworkList.tsx": {
        '{networks.length} networks': '{networks.length} 网络',
        '{pruning ? "pruning…" : "prune"}': '{pruning ? "清理中…" : "清理"}',
        '>No networks<': '>无网络<',
        'title="Remove network"': 'title="移除网络"',
    },
    "src/plugins/docker/components/LogsView.tsx": {
        '"Disable auto-scroll"': '"关闭自动滚动"',
        '"Enable auto-scroll"': '"开启自动滚动"',
        '>Waiting for logs…<': '>等待日志…<',
    },
    "src/plugins/docker/components/ContainerRow.tsx": {
        '`Pull failed: ${e}`': '`拉取失败: ${e}`',
        'title="Start"': 'title="启动"',
        'title="Stop"': 'title="停止"',
        'title="Restart"': 'title="重启"',
        'title="Pause"': 'title="暂停"',
        'title="Resume"': 'title="恢复"',
        'title="Logs"': 'title="日志"',
        'title="Copy docker run command"': 'title="复制 docker run 命令"',
        '"Pull update and recreate this container"': '"拉取更新并重建此容器"',
        '"Pull newer image"': '"拉取更新的镜像"',
        'title="Open terminal"': 'title="打开终端"',
        'title="Remove"': 'title="移除"',
    },
    "src/plugins/docker/components/ContainerList.tsx": {
        ').length} running': ').length} 运行中',
        'title="Check containers for image updates"': 'title="检查容器的镜像更新"',
        '{isChecking ? "checking…" : "updates"}': '{isChecking ? "检查中…" : "更新"}',
        '>\n            all\n          </button>': '>\n            全部\n          </button>',
        '"No containers"': '"无容器"',
        '"No running containers"': '"无运行中的容器"',
    },
    "src/plugins/docker/components/ImageList.tsx": {
        '{images.length} images': '{images.length} 镜像',
        '· {outdatedCount} outdated': '· {outdatedCount} 个待更新',
        'title="Check all images for registry updates"': 'title="检查所有镜像的 registry 更新"',
        '{isChecking ? "checking…" : "check updates"}': '{isChecking ? "检查中…" : "检查更新"}',
        '{pruning ? "pruning…" : "prune"}': '{pruning ? "清理中…" : "清理"}',
        '>No images<': '>无镜像<',
        '`Pull failed: ${e}`': '`拉取失败: ${e}`',
        '`Pull ${tag} and recreate its containers`': '`拉取 ${tag} 并重建其容器`',
        '`Pull newer image for ${tag}`': '`为 ${tag} 拉取更新的镜像`',
        '{pulling ? (recreateAfterPull ? "updating…" : "pulling…") : recreateAfterPull ? "update" : "pull"}':
            '{pulling ? (recreateAfterPull ? "更新中…" : "拉取中…") : recreateAfterPull ? "更新" : "拉取"}',
        'title="Remove image"': 'title="移除镜像"',
    },
    "src/plugins/docker/components/StackList.tsx": {
        '`Updated stack ${stackName}`': '`已更新编排栈 ${stackName}`',
        '`Stack update failed: ${e}`': '`编排栈更新失败: ${e}`',
        '{stacks.length} stacks': '{stacks.length} 编排栈',
        "title=\"Check the expanded stack's services for image updates\"": 'title="检查展开编排栈的服务镜像更新"',
        '{isChecking ? "checking…" : "updates"}': '{isChecking ? "检查中…" : "更新"}',
        '>No Compose stacks<': '>无 Compose 编排栈<',
        '`${stack.running}/${stack.total} running`': '`${stack.running}/${stack.total} 运行中`',
        'title="Up"': 'title="启动"',
        'title="Stop"': 'title="停止"',
        'title="Restart"': 'title="重启"',
        'title="Update stack (compose pull + up -d)"': 'title="更新编排栈 (compose pull + up -d)"',
        'title="Compose logs"': 'title="Compose 日志"',
        'title="Down"': 'title="停止并移除"',
        '>No services<': '>无服务<',
        'title="Pause"': 'title="暂停"',
        'title="Unpause"': 'title="恢复"',
        'title="Start"': 'title="启动"',
        'title="Logs"': 'title="日志"',
        'title="Open terminal"': 'title="打开终端"',
    },
    "src/plugins/docker/components/DockerPanel.tsx": {
        'label: "Containers"': 'label: "容器"',
        'label: "Images"': 'label: "镜像"',
        'label: "Volumes"': 'label: "数据卷"',
        'label: "Networks"': 'label: "网络"',
        'label: "Stacks"': 'label: "编排栈"',
        '>No active session<': '>无活动会话<',
        ">Local Docker isn't available on Android</h3>": '>Android 上无法使用本地 Docker</h3>',
        'Connect to a host over SSH to manage its Docker.': '通过 SSH 连接到主机以管理其 Docker。',
        '>Docker is not reachable</h3>': '>无法连接到 Docker</h3>',
        'Start Docker in this environment, then refresh.': '在此环境中启动 Docker，然后刷新。',
        '\n            Refresh\n          </button>': '\n            刷新\n          </button>',
        'title="Refresh"': 'title="刷新"',
        'title="System prune (docker system prune -a)"': 'title="系统清理 (docker system prune -a)"',
    },

    # ═══════════════════════════ Proxmox ═══════════════════════════
    "src/plugins/proxmox/components/ProxmoxPanel.tsx": {
        '"No active session"': '"无活动会话"',
        '"Proxmox VE not detected"': '"未检测到 Proxmox VE"',
        '"This panel requires an SSH connection to a Proxmox VE host."': '"此面板需要 SSH 连接到 Proxmox VE 主机。"',
        '"Refresh"': '"刷新"',
    },
    "src/plugins/proxmox/components/LxcList.tsx": {
        '`${running} running`': '`${running} 运行中`',
        '"No containers"': '"无容器"',
        '"Start"': '"启动"',
        '"Stop"': '"停止"',
        '"Restart"': '"重启"',
        '"Open shell"': '"打开终端"',
        '"Snapshots"': '"快照"',
        '`Action failed: ${e}`': '`操作失败: ${e}`',
    },
    "src/plugins/proxmox/components/SnapshotList.tsx": {
        '"Snapshot name"': '"快照名称"',
        '"Create snapshot"': '"创建快照"',
        '"Description (optional)"': '"描述（可选）"',
        '"No snapshots"': '"无快照"',
        '"Rollback to this snapshot"': '"回滚到此快照"',
        '"Delete snapshot"': '"删除快照"',
        '`Snapshot failed: ${e}`': '`快照失败: ${e}`',
        '`Rollback failed: ${e}`': '`回滚失败: ${e}`',
        '`Delete failed: ${e}`': '`删除失败: ${e}`',
    },

    # ═══════════════════════════ Monitoring ═══════════════════════════
    "src/plugins/monitoring/components/MetricsPanel.tsx": {
        '"No active session"': '"无活动会话"',
        '"Live metrics for this device aren\'t available on Android. Connect to a host over SSH to see its metrics."':
            '"此设备的实时指标在 Android 上不可用。通过 SSH 连接到主机以查看其指标。"',
        '"Live metrics are not available for serial sessions."': '"串口会话不支持实时指标。"',
    },
    "src/plugins/monitoring/components/SystemInfoSection.tsx": {
        '"System Info"': '"系统信息"',
        '"Loading…"': '"加载中…"',
        '"Cores"': '"核心"',
        '"Arch"': '"架构"',
        '"Host"': '"主机"',
        '"Kernel"': '"内核"',
    },
    "src/plugins/monitoring/components/DiskSection.tsx": {
        '"Disk"': '"磁盘"',
    },

    # ═══════════════════════════ Process Manager ═══════════════════════════
    "src/plugins/process-manager/components/ProcessPanel.tsx": {
        '"No active session"': '"无活动会话"',
        '"The process list for this device isn\'t available on Android. Connect to a host over SSH to see its processes."':
            '"此设备的进程列表在 Android 上不可用。通过 SSH 连接到主机以查看其进程。"',
        '"Filter processes…"': '"过滤进程…"',
        '"Name"': '"名称"',
        '"User"': '"用户"',
        '"Mem"': '"内存"',
        '"Kill"': '"终止"',
        '"Cancel"': '"取消"',
        '`Kill process ${entry.pid}`': '`终止进程 ${entry.pid}`',
        '"No processes found"': '"未找到进程"',
    },
}
