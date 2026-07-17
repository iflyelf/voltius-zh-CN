import i18n from "@/i18n";
import type { ConnectionExport } from "../formats";

// 新格式: Groups,Label,Tags,Hostname/IP,Protocol,Port,Username,Password
const CSV_HEADERS_NEW = ["Groups", "Label", "Tags", "Hostname/IP", "Protocol", "Port", "Username", "Password"];

function csvEscape(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

export function connectionsToCSV(connections: ConnectionExport[]): string {
  const rows: string[][] = [CSV_HEADERS_NEW];
  for (const c of connections) {
    // 从 tags 中提取 __group:xxx__ 特殊标签作为 Groups
    const groupTag = c.tags.find((t) => t.startsWith("__group:") && t.endsWith("__"));
    const groups = groupTag ? groupTag.slice(8, -2) : "";
    const regularTags = c.tags.filter((t) => !(t.startsWith("__group:") && t.endsWith("__")));
    
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

  // 支持多种列名映射
  const hostIdx = col("hostname/ip") >= 0 ? col("hostname/ip") : 
                  col("hostname") >= 0 ? col("hostname") : col("host");
  const usernameIdx = col("username") >= 0 ? col("username") : col("user");
  const nameIdx = col("label") >= 0 ? col("label") : col("name");
  const groupsIdx = col("groups") >= 0 ? col("groups") : col("group");
  const tagsIdx = col("tags");
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

    connections.push({
      name: nameIdx >= 0 ? row[nameIdx]?.trim() || undefined : undefined,
      host,
      port: portIdx >= 0 ? parseInt(row[portIdx], 10) || 22 : 22,
      username,
      password: passwordIdx >= 0 ? row[passwordIdx]?.trim() || undefined : undefined,
      auth_type: "password", // CSV 导入默认密码认证
      tags,
    });
  }
  return connections;
}
