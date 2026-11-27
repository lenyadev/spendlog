import js from "@eslint/js";
import ts from "typescript-eslint";
import svelte from "eslint-plugin-svelte";
import prettier from "eslint-config-prettier";
import globals from "globals";

export default ts.config(
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs["flat/recommended"],
  prettier,
  ...svelte.configs["flat/prettier"],
  {
    languageOptions: { globals: { ...globals.browser } },
  },
  {
    files: ["**/*.svelte", "**/**.svelte.ts"],
    languageOptions: { parserOptions: { parser: ts.parser } },
  },
  {
    ignores: ["dist/", "node_modules/", "src/lib/api/schema.d.ts"],
  },
);
