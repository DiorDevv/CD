import { useState } from "react";
import { ShieldAlert, DatabaseZap } from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionPanel } from "@/pages/SectionPanel";

export function SocDashboardPage() {
  return (
    <SectionPanel
      section="soc"
      title="SOC boshqaruv paneli"
      description="Security Operations Center — topshiriqlar va bo'lim monitoringi."
      icon={ShieldAlert}
    />
  );
}

export function DlpDashboardPage() {
  return (
    <SectionPanel
      section="dlp"
      title="DLP boshqaruv paneli"
      description="Data Loss Prevention — topshiriqlar va bo'lim monitoringi."
      icon={DatabaseZap}
    />
  );
}

export function ViewerDashboardPage() {
  const [section, setSection] = useState<"soc" | "dlp">("soc");
  return (
    <div>
      <div className="mb-3 flex items-center gap-1 rounded-md border border-line-strong p-0.5 w-fit">
        {(["soc", "dlp"] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSection(s)}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium transition-colors",
              section === s
                ? "bg-accent-soft text-content"
                : "text-content-muted hover:text-content",
            )}
          >
            {s.toUpperCase()}
          </button>
        ))}
      </div>
      {section === "soc" ? (
        <SectionPanel
          section="soc"
          title="SOC — kuzatuv ko'rinishi"
          description="Faqat o'qish. Shaxsiy topshiriqlaringizni yozib qo'yishingiz mumkin."
          icon={ShieldAlert}
        />
      ) : (
        <SectionPanel
          section="dlp"
          title="DLP — kuzatuv ko'rinishi"
          description="Faqat o'qish. Shaxsiy topshiriqlaringizni yozib qo'yishingiz mumkin."
          icon={DatabaseZap}
        />
      )}
    </div>
  );
}
