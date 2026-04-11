import nextConfig from "eslint-config-next";

const eslintConfig = [
  ...nextConfig.map((config) => {
    if (config.name === "next") {
      return {
        ...config,
        rules: {
          ...config.rules,
          "react-hooks/set-state-in-effect": "off",
          "react-hooks/refs": "off",
          "react-hooks/purity": "off",
        },
      };
    }
    if (config.name === "next/typescript") {
      return {
        ...config,
        rules: {
          ...config.rules,
          "react-hooks/exhaustive-deps": "warn",
        },
      };
    }
    if (config.name === "default-ignores") {
      return {
        ...config,
        ignores: [...(config.ignores || []), "tests/**"],
      };
    }
    return config;
  }),
  // Ignore test files
  {
    ignores: ["tests/**"],
  },
];

export default eslintConfig;
