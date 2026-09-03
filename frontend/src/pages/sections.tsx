import { ShieldAlert, DatabaseZap, Eye } from "lucide-react";
import { PlaceholderDashboard } from "@/pages/PlaceholderDashboard";

export function SocDashboardPage() {
  return (
    <PlaceholderDashboard
      title="SOC boshqaruv paneli"
      description="Security Operations Center — hodisalar, ogohlantirishlar va monitoring."
      section="SOC"
      icon={ShieldAlert}
      panels={["Faol ogohlantirishlar", "Hodisalar navbati", "Sensor holati"]}
    />
  );
}

export function DlpDashboardPage() {
  return (
    <PlaceholderDashboard
      title="DLP boshqaruv paneli"
      description="Data Loss Prevention — siyosatlar, buzilishlar va kanallar nazorati."
      section="DLP"
      icon={DatabaseZap}
      panels={["Siyosat buzilishlari", "Kanal nazorati", "Karantindagi fayllar"]}
    />
  );
}

export function ViewerDashboardPage() {
  return (
    <PlaceholderDashboard
      title="Umumiy monitoring ko'rinishi"
      description="SOC va DLP bo'limlari bo'yicha yig'ma ma'lumot — faqat kuzatish uchun."
      section="SOC + DLP"
      icon={Eye}
      readOnly
      panels={["SOC xulosa", "DLP xulosa", "Tizim salomatligi"]}
    />
  );
}
