import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

// Flat-config ESLint setup using the SPLIT @typescript-eslint packages
// (parser + plugin) instead of the `typescript-eslint` umbrella package.
// audit-A3 finding #2: the umbrella `typescript-eslint` was imported but
// never listed in package.json devDependencies, which would cause
// `npm run lint` to fail with ERR_MODULE_NOT_FOUND. Using the split
// packages directly removes the missing-dep without adding a new one.
export default [
  { ignores: ["dist", "node_modules"] },
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parser: tsParser,
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
];
