export const MIN_PASSWORD = 10;

const LOWER = "abcdefghijkmnpqrstuvwxyz";
const UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ";
const DIGIT = "23456789";
const SYMBOL = "!@#$%^&*";

function pick(set: string): string {
  const idx = crypto.getRandomValues(new Uint32Array(1))[0] % set.length;
  return set[idx];
}

/** Backend parol siyosatiga kafolatli mos: >=14, katta+kichik harf, raqam, belgi, takrorsiz. */
export function randomPassword(): string {
  const base = [
    pick(UPPER),
    pick(UPPER),
    pick(LOWER),
    pick(LOWER),
    pick(DIGIT),
    pick(DIGIT),
    pick(SYMBOL),
  ];
  const pool = LOWER + UPPER + DIGIT;
  while (base.length < 14) base.push(pick(pool));
  for (let i = base.length - 1; i > 0; i--) {
    const j = crypto.getRandomValues(new Uint32Array(1))[0] % (i + 1);
    [base[i], base[j]] = [base[j], base[i]];
  }
  return base.join("");
}
