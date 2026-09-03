import {
  ClipboardList,
  FileText,
  HardDrive,
  ShieldAlert,
  Table2,
  type LucideIcon,
} from "lucide-react";
import type { ColumnType } from "@/lib/types";
import { newColumnDraft, type ColumnDraft } from "@/lib/dynamic";

interface TemplateColumn {
  label: string;
  type: ColumnType;
  required?: boolean;
  options?: { label: string; value: string; color?: string }[];
  min?: number;
  max?: number;
  default?: string | boolean;
}

export interface TableTemplate {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  /** Jadval nomi uchun taklif (bo'sh bo'lsa foydalanuvchi kiritadi) */
  suggestedName?: string;
  columns: TemplateColumn[];
}

export const TABLE_TEMPLATES: TableTemplate[] = [
  {
    id: "blank",
    name: "Bo'sh jadval",
    description: "Ustunlarni o'zingiz qo'shasiz",
    icon: Table2,
    columns: [],
  },
  {
    id: "incidents",
    name: "Hodisalar jurnali",
    description: "SOC hodisalarini kuzatish",
    icon: ShieldAlert,
    suggestedName: "Hodisalar jurnali",
    columns: [
      { label: "Sarlavha", type: "text", required: true },
      {
        label: "Darajasi",
        type: "select",
        required: true,
        options: [
          { label: "Past", value: "low", color: "#22c55e" },
          { label: "O'rta", value: "medium", color: "#f59e0b" },
          { label: "Yuqori", value: "high", color: "#ef4444" },
          { label: "Kritik", value: "critical", color: "#a855f7" },
        ],
      },
      {
        label: "Holati",
        type: "select",
        options: [
          { label: "Yangi", value: "new", color: "#4f7cff" },
          { label: "Tekshirilmoqda", value: "investigating", color: "#f59e0b" },
          { label: "Yopilgan", value: "closed", color: "#64748b" },
        ],
        default: "new",
      },
      { label: "Mas'ul", type: "user" },
      { label: "Aniqlangan vaqti", type: "datetime" },
      { label: "Tavsif", type: "long_text" },
    ],
  },
  {
    id: "assets",
    name: "Aktivlar ro'yxati",
    description: "Server, ish stansiyalari, qurilmalar",
    icon: HardDrive,
    suggestedName: "Aktivlar",
    columns: [
      { label: "Nomi", type: "text", required: true },
      { label: "IP manzil", type: "text" },
      {
        label: "Turi",
        type: "select",
        options: [
          { label: "Server", value: "server", color: "#4f7cff" },
          { label: "Ish stansiyasi", value: "workstation", color: "#22c55e" },
          { label: "Tarmoq qurilmasi", value: "network", color: "#a855f7" },
          { label: "Mobil", value: "mobile", color: "#ec4899" },
        ],
      },
      { label: "Egasi", type: "user" },
      { label: "Faol", type: "boolean", default: true },
      { label: "Oxirgi tekshiruv", type: "date" },
    ],
  },
  {
    id: "tasks",
    name: "Vazifalar",
    description: "Jamoa vazifalarini boshqarish",
    icon: ClipboardList,
    suggestedName: "Vazifalar",
    columns: [
      { label: "Vazifa", type: "text", required: true },
      {
        label: "Holati",
        type: "select",
        options: [
          { label: "Rejada", value: "todo", color: "#64748b" },
          { label: "Jarayonda", value: "doing", color: "#f59e0b" },
          { label: "Bajarildi", value: "done", color: "#22c55e" },
        ],
        default: "todo",
      },
      {
        label: "Muhimlik",
        type: "select",
        options: [
          { label: "Past", value: "low", color: "#22c55e" },
          { label: "O'rta", value: "mid", color: "#f59e0b" },
          { label: "Yuqori", value: "high", color: "#ef4444" },
        ],
      },
      { label: "Ijrochi", type: "user" },
      { label: "Muddat", type: "date" },
      { label: "Izoh", type: "long_text" },
    ],
  },
  {
    id: "access_requests",
    name: "Ruxsat so'rovlari",
    description: "Tizimlarga kirish so'rovlari",
    icon: FileText,
    suggestedName: "Ruxsat so'rovlari",
    columns: [
      { label: "So'rovchi", type: "user", required: true },
      { label: "Tizim / resurs", type: "text", required: true },
      {
        label: "Ruxsat darajasi",
        type: "select",
        options: [
          { label: "O'qish", value: "read" },
          { label: "Yozish", value: "write" },
          { label: "Admin", value: "admin", color: "#ef4444" },
        ],
      },
      {
        label: "Holati",
        type: "select",
        options: [
          { label: "Kutilmoqda", value: "pending", color: "#f59e0b" },
          { label: "Tasdiqlandi", value: "approved", color: "#22c55e" },
          { label: "Rad etildi", value: "rejected", color: "#ef4444" },
        ],
        default: "pending",
      },
      { label: "So'ralgan sana", type: "date" },
      { label: "Asos", type: "long_text" },
    ],
  },
];

/** Shablon ustunlarini tahrirlanadigan qoralamalarga aylantiradi. */
export function templateToDrafts(tpl: TableTemplate): ColumnDraft[] {
  return tpl.columns.map((c) => {
    const d = newColumnDraft(c.type);
    d.label = c.label;
    d.required = !!c.required;
    if (c.options) {
      d.options = c.options.map((o) => ({ ...o }));
    }
    if (c.min != null) d.min = String(c.min);
    if (c.max != null) d.max = String(c.max);
    if (c.default != null) d.default = c.default;
    return d;
  });
}
