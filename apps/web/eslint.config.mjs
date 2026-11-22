import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Prefer native flat exports from eslint-config-next@16 when available.
const nativeFlat = Array.isArray(nextVitals) ? [...nextVitals, ...(Array.isArray(nextTs) ? nextTs : [])] : null;

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = nativeFlat ?? [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

eslintConfig.push({
  ignores: [".next/**", "node_modules/**", "out/**"],
});

export default eslintConfig;
