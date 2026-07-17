import i18n from "@/i18n";
import { fromJSON, detectFormat } from "./formats";
import type { ConnectionExport, ExportBundle, FolderExport } from "./formats";
import { connectionsFromCSV } from "./parsers/csv";
import { connectionsFromMobaXterm, extractMobaXtermBundle } from "./parsers/mobaxterm";
import { bundleFromTermius, extractTermiusBundle } from "./parsers/termius";

export interface Importer {
  key: string;
  label: string;
  icon: string;
  sub: string;
  fileAccept: string;
  hint?: string;
  placeholder: string;
  parse(text: string): ExportBundle;
  /** Optional: one-step extraction from a locally-installed source app. */
  autoExtract?(): Promise<ExportBundle>;
}

function connectionsOnlyBundle(connections: ConnectionExport[]): ExportBundle {
  // 汉化版: 从 __group:xxx__ 特殊 tag 提取分组,生成文件夹并关联连接
  const groupMap = new Map<string, string>(); // group path → folder _eid
  const folders: FolderExport[] = [];
  
  for (const conn of connections) {
    const groupTag = conn.tags.find((t) => t.startsWith("__group:") && t.endsWith("__"));
    if (groupTag) {
      const groupPath = groupTag.slice(8, -2); // 提取 "me/Papa"
      if (!groupMap.has(groupPath)) {
        const eid = `folder:${groupPath}`;
        groupMap.set(groupPath, eid);
        folders.push({
          _eid: eid,
          name: groupPath, // 简化: 全路径作为名称(如 "me/Papa")
          object_type: "connection",
        });
      }
      // 关联连接到文件夹
      conn._folder_eid = groupMap.get(groupPath);
      // 移除特殊 tag (已转为文件夹)
      conn.tags = conn.tags.filter((t) => t !== groupTag);
    }
  }
  
  return { version: 1, exported_at: "", folders, connections, identities: [], keys: [], snippets: [], portForwardingRules: [] };
}

export const IMPORTERS: Importer[] = [
  {
    key: "voltius",
    label: "Voltius JSON",
    icon: "lucide:braces",
    sub: "JSON",
    fileAccept: ".json",
    placeholder: 'Paste Voltius JSON here, or drop a .json file…\n\n{ "version": 1, "connections": [...] }',
    parse: fromJSON,
  },
  {
    key: "csv",
    label: "CSV",
    icon: "lucide:table-2",
    sub: "Spreadsheet",
    fileAccept: ".csv,.txt",
    placeholder: "Paste CSV here, or drop a file…\n\nname,host,port,username,auth_type,tags",
    parse: (text) => connectionsOnlyBundle(connectionsFromCSV(text)),
  },
  {
    key: "mobaxterm",
    label: "MobaXterm",
    icon: "custom:mobaxterm",
    sub: "Local install · auto-decrypt",
    fileAccept: ".ini,.mxtsessions,.mobaconf,.txt",
    hint: "Requires MobaXterm to be installed (Windows only).",
    placeholder: "Drop MobaXterm.ini here, or paste its contents…",
    parse: (text) => connectionsOnlyBundle(connectionsFromMobaXterm(text)),
    autoExtract: extractMobaXtermBundle,
  },
  {
    key: "termius",
    label: "Termius",
    icon: "simple-icons:termius",
    sub: "Local install · auto-extract",
    fileAccept: ".json",
    hint: "Requires Termius to be installed and logged in.",
    placeholder: "Use Auto Extract for Termius. Pasted legacy Termius dumps are not supported for faithful import.",
    parse: bundleFromTermius,
    autoExtract: extractTermiusBundle,
  },
];

export function parseImport(text: string): ExportBundle | "encrypted" {
  const detected = detectFormat(text.trim());
  if (detected === "voltius-encrypted") return "encrypted";
  if (detected === "json") return fromJSON(text);
  if (detected === "csv") return connectionsOnlyBundle(connectionsFromCSV(text));
  if (detected === "mobaxterm") return connectionsOnlyBundle(connectionsFromMobaXterm(text));
  if (detected === "termius") return bundleFromTermius(text);
  throw new Error(i18n.t("common.error.couldNotDetectFormat"));
}
