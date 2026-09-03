import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DirectoryUser } from "@/lib/types";

let cache: DirectoryUser[] | null = null;
let inflight: Promise<DirectoryUser[]> | null = null;

async function fetchDirectory(): Promise<DirectoryUser[]> {
  if (cache) return cache;
  if (!inflight) {
    inflight = api
      .get<DirectoryUser[]>("/users/directory")
      .then((r) => {
        cache = r.data;
        inflight = null;
        return cache;
      })
      .catch((e) => {
        inflight = null;
        throw e;
      });
  }
  return inflight;
}

export function invalidateDirectory() {
  cache = null;
}

/** `user` turidagi ustunlar uchun foydalanuvchilar ro'yxati (bir marta yuklanadi). */
export function useDirectory() {
  const [users, setUsers] = useState<DirectoryUser[]>(cache ?? []);
  const [loading, setLoading] = useState(cache === null);

  useEffect(() => {
    let alive = true;
    if (cache) {
      setUsers(cache);
      setLoading(false);
      return;
    }
    fetchDirectory()
      .then((u) => alive && (setUsers(u), setLoading(false)))
      .catch(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const byId = new Map(users.map((u) => [u.id, u]));
  return { users, byId, loading };
}
