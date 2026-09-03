import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import type { Role } from "@/lib/types";

const mockUseAuth = vi.fn();
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

function renderAt(
  path: string,
  state: {
    status: string;
    user: { role: Role; must_change_password: boolean } | null;
  },
  roles?: Role[],
) {
  mockUseAuth.mockReturnValue(state);
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<ProtectedRoute roles={roles} />}>
          <Route path="/secret" element={<div>MAXFIY</div>} />
        </Route>
        <Route path="/login" element={<div>LOGIN SAHIFA</div>} />
        <Route path="/change-password" element={<div>PAROL SAHIFA</div>} />
        <Route path="/super-admin/dashboard" element={<div>SUPER DASH</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  it("yuklanayotganda spinner ko'rsatadi", () => {
    renderAt("/secret", { status: "loading", user: null });
    expect(screen.queryByText("MAXFIY")).not.toBeInTheDocument();
  });

  it("anonim foydalanuvchini /login ga yo'naltiradi", () => {
    renderAt("/secret", { status: "anonymous", user: null });
    expect(screen.getByText("LOGIN SAHIFA")).toBeInTheDocument();
  });

  it("must_change_password bo'lsa /change-password ga yo'naltiradi", () => {
    renderAt("/secret", {
      status: "authenticated",
      user: { role: "viewer", must_change_password: true },
    });
    expect(screen.getByText("PAROL SAHIFA")).toBeInTheDocument();
  });

  it("roli mos kelmasa o'z dashboard'iga yo'naltiradi", () => {
    renderAt(
      "/secret",
      {
        status: "authenticated",
        user: { role: "super_admin", must_change_password: false },
      },
      ["viewer"],
    );
    expect(screen.getByText("SUPER DASH")).toBeInTheDocument();
  });

  it("hammasi joyida bo'lsa himoyalangan sahifani ko'rsatadi", () => {
    renderAt(
      "/secret",
      {
        status: "authenticated",
        user: { role: "viewer", must_change_password: false },
      },
      ["viewer"],
    );
    expect(screen.getByText("MAXFIY")).toBeInTheDocument();
  });
});
