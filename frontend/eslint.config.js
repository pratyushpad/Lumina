import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // React Compiler rule: flags any impure call (Date.now(), Math.random())
      // inside a component, including event handlers where it is correct and
      // unavoidable. This project does not compile with the React Compiler, so
      // the rule only produces false positives here.
      "react-hooks/purity": "off",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Unused vars are errors, but an underscore prefix marks a deliberate discard.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // The API client returns parsed JSON; blanket `any` should be opt-in, not default.
      "@typescript-eslint/no-explicit-any": "warn",
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
);
