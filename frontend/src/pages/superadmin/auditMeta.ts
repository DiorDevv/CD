import type { BadgeProps } from "@/components/ui/badge";

export const ACTION_LABELS: Record<string, string> = {
  login: "Tizimga kirdi",
  login_failed: "Kirish urinishi muvaffaqiyatsiz",
  logout: "Tizimdan chiqdi",
  token_refreshed: "Token yangilandi",
  token_reuse_detected: "Token qayta ishlatish aniqlandi",
  password_changed: "Parol o'zgartirildi",
  password_reset: "Parol tiklandi (admin)",
  user_created: "Foydalanuvchi yaratildi",
  user_blocked: "Foydalanuvchi bloklandi",
  user_unblocked: "Foydalanuvchi faollashtirildi",
  user_deleted: "Foydalanuvchi o'chirildi",
  account_locked: "Hisob vaqtincha qulflandi",
};

type Variant = NonNullable<BadgeProps["variant"]>;

export const ACTION_VARIANT: Record<string, Variant> = {
  login: "success",
  login_failed: "warning",
  account_locked: "danger",
  token_reuse_detected: "danger",
  user_created: "accent",
  user_blocked: "danger",
  user_unblocked: "success",
  user_deleted: "danger",
  password_changed: "accent",
  password_reset: "warning",
  logout: "neutral",
  token_refreshed: "neutral",
};

export const ALL_ACTIONS = Object.keys(ACTION_LABELS);
