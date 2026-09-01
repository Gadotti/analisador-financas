/**
 * Jest em ESM nativo — sem Babel e sem transform.
 *
 * O runner precisa da flag --experimental-vm-modules, já embutida nos scripts
 * do package.json.
 */
export default {
  testEnvironment: "node",
  testMatch: ["<rootDir>/test/**/*.test.js"],
  // helpers/ guarda utilitários compartilhados, não casos de teste.
  testPathIgnorePatterns: ["/node_modules/", "<rootDir>/test/helpers/"],

  collectCoverageFrom: ["src/**/*.js"],
  coverageDirectory: "coverage",
  coverageReporters: ["text-summary", "text"],

  // Alguns testes sobem servidores e processos filhos.
  testTimeout: 30_000,
  clearMocks: true,
};
