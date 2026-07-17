import i18n from "@/i18n";
import type { ConnectionExport, FolderExport } from "../formats";

// 导出格式: Groups,Label,Tags,Hostname/IP,Protocol,Port,Username,Password
// 导入兼容: 上述格式 + 含 Notes 列的变体 + 旧格式(name/host/port/username)
const CSV_HEADERS_NEW = ["Groups", "Label", "Tags", "Hostname/IP", "Protocol", "Port", "Username", "Password"];

function csvEscape(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

// 根据文件夹层级重建完整路径(如 测试/测试1/测试2)
function buildFolderPathMap(folders: FolderExport[]): Map<string, string> {
  const byEid = new Map(folders.map((f) => [f._eid, f]));
  const pathCache = new Map<string, string>();
  const resolve = (eid: string): string => {
    if (pathCache.has(eid)) return pathCache.get(eid)!;
    const f = byEid.get(eid);
    if (!f) return "";
    const path = f.parent_folder_eid
      ? `${resolve(f.parent_folder_eid)}/${f.name}`
      : f.name;
    pathCache.set(eid, path);
    return path;
  };
  const map = new Map<string, string>();
  for (const f of folders) map.set(f._eid, resolve(f._eid));
  return map;
}

export function connectionsToCSV(connections: ConnectionExport[], folders: FolderExport[] = []): string {
  const folderPathMap = buildFolderPathMap(folders);
  const rows: string[][] = [CSV_HEADERS_NEW];
  for (const c of connections) {
    // Groups 来源优先级: 文件夹层级路径 > __group:xxx__ 特殊标签
    let groups = "";
    if (c._folder_eid && folderPathMap.has(c._folder_eid)) {
      groups = folderPathMap.get(c._folder_eid)!;
    } else {
      const groupTag = c.tags.find((t) => t.startsWith("__group:") && t.endsWith("__"));
      if (groupTag) groups = groupTag.slice(8, -2);
    }
    const regularTags = c.tags.filter((t) =>
      !(t.startsWith("__group:") && t.endsWith("__")) &&
      !(t.startsWith("__note:") && t.endsWith("__"))
    );

    rows.push([
      groups,                           // Groups
      c.name ?? "",                     // Label
      regularTags.join(";"),            // Tags
      c.host ?? "",                     // Hostname/IP
      "ssh",                            // Protocol
      String(c.port ?? 22),             // Port
      c.username ?? "",                 // Username
      c.password ?? "",                 // Password
    ]);
  }
  return rows.map((r) => r.map(csvEscape).join(",")).join("\n");
}

function parseCSVRow(line: string): string[] {
  const result: string[] = [];
  let i = 0;
  while (i <= line.length) {
    if (i === line.length) { result.push(""); break; }
    if (line[i] === '"') {
      let value = "";
      i++;
      while (i < line.length) {
        if (line[i] === '"' && line[i + 1] === '"') { value += '"'; i += 2; }
        else if (line[i] === '"') { i++; break; }
        else { value += line[i++]; }
      }
      result.push(value);
      if (line[i] === ",") i++;
    } else {
      const end = line.indexOf(",", i);
      if (end === -1) { result.push(line.slice(i)); break; }
      result.push(line.slice(i, end));
      i = end + 1;
    }
  }
  return result;
}

export function connectionsFromCSV(text: string): ConnectionExport[] {
  const lines = text.trim().split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return [];
  const headers = parseCSVRow(lines[0]).map((h) => h.toLowerCase().trim());
  const col = (name: string) => headers.indexOf(name);

  // 灵活列名映射(支持多种字段变体, 含/不含 Notes)
  const hostIdx = col("hostname/ip") >= 0 ? col("hostname/ip") :
                  col("hostname") >= 0 ? col("hostname") : col("host");
  const usernameIdx = col("username") >= 0 ? col("username") : col("user");
  const nameIdx = col("label") >= 0 ? col("label") : col("name");
  const groupsIdx = col("groups") >= 0 ? col("groups") : col("group");
  const tagsIdx = col("tags");
  const notesIdx = col("notes") >= 0 ? col("notes") : col("note");
  const portIdx = col("port");
  const passwordIdx = col("password");

  if (hostIdx === -1 || usernameIdx === -1) {
    throw new Error(i18n.t("common.error.csvMissingColumns"));
  }

  const connections: ConnectionExport[] = [];
  for (let i = 1; i < lines.length; i++) {
    const row = parseCSVRow(lines[i]);
    const host = row[hostIdx]?.trim();
    const username = row[usernameIdx]?.trim();
    if (!host || !username) continue;

    // 处理 tags: 合并普通 tags 和 Groups
    const tags: string[] = [];
    if (tagsIdx >= 0 && row[tagsIdx]?.trim()) {
      tags.push(...row[tagsIdx].trim().split(";").map((t) => t.trim()).filter(Boolean));
    }
    // Groups 存为特殊 tag: __group:me/Papa__
    if (groupsIdx >= 0 && row[groupsIdx]?.trim()) {
      tags.push(`__group:${row[groupsIdx].trim()}__`);
    }

    // Notes 列(如有)存为特殊 tag __note:xxx__(ConnectionFormData 无 notes 字段)
    if (notesIdx >= 0 && row[notesIdx]?.trim()) {
      tags.push(`__note:${row[notesIdx].trim()}__`);
    }

    const conn: ConnectionExport = {
      name: nameIdx >= 0 ? row[nameIdx]?.trim() || undefined : undefined,
      host,
      port: portIdx >= 0 ? parseInt(row[portIdx], 10) || 22 : 22,
      username,
      password: passwordIdx >= 0 ? row[passwordIdx]?.trim() || undefined : undefined,
      auth_type: "password", // CSV 导入默认密码认证
      tags,
    };
    connections.push(conn);
  }
  return connections;
}
