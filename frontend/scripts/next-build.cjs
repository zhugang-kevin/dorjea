/* eslint-disable @typescript-eslint/no-require-imports */
const { spawn, spawnSync } = require("node:child_process");
const { existsSync, readFileSync, writeFileSync, unlinkSync } = require("node:fs");
const { dirname, join } = require("node:path");

const env = { ...process.env };
const buildPathFile = join(process.cwd(), ".next-build-path");
const tsconfigPath = join(process.cwd(), "tsconfig.json");
const originalTsconfig = existsSync(tsconfigPath) ? readFileSync(tsconfigPath, "utf8") : null;
if (!env.NEXT_DIST_DIR) {
  env.NEXT_DIST_DIR = `.next-build-${Date.now()}`;
}

const nextBin = require.resolve("next/dist/bin/next");
const tscBin = join(dirname(require.resolve("typescript/package.json")), "bin", "tsc");
const eslintBin = join(dirname(require.resolve("eslint/package.json")), "bin", "eslint.js");
const args = [nextBin, "build", "--webpack", ...process.argv.slice(2)];
const tsNoCheckPath = join(process.cwd(), ".next-build-tsconfig.json");

function runPreflight(label, bin, binArgs) {
  const result = spawnSync(process.execPath, [bin, ...binArgs], {
    stdio: "inherit",
    env,
  });
  if (result.error) {
    throw new Error(`${label} failed to start: ${result.error.message}`);
  }
  if ((result.status ?? 0) !== 0) {
    process.exit(result.status ?? 1);
  }
}

runPreflight("TypeScript preflight", tscBin, ["--noEmit"]);
runPreflight("ESLint preflight", eslintBin, ["."]);

if (originalTsconfig !== null) {
  const parsed = JSON.parse(originalTsconfig);
  parsed.include = parsed.include || [];
  parsed.exclude = Array.isArray(parsed.exclude) ? parsed.exclude : ["node_modules"];
  // Keep Next build from trying to run worker-based TS validation against generated build dirs.
  parsed.exclude = Array.from(new Set([...parsed.exclude, ".next-build*", ".next*", ".next-runtime*"]));
  writeFileSync(tsNoCheckPath, JSON.stringify(parsed, null, 2), "utf8");
  env.TS_NODE_PROJECT = tsNoCheckPath;
  env.NEXT_DISABLE_TS_BUILD_WORKER = "1";
  env.NEXT_DISABLE_ESLINT = "1";
}

const child = spawn(process.execPath, args, {
  stdio: "inherit",
  env,
});

let restoredTsconfig = false;
function restoreTsconfig() {
  if (restoredTsconfig) {
    return;
  }
  restoredTsconfig = true;
  if (originalTsconfig !== null) {
    writeFileSync(tsconfigPath, originalTsconfig, "utf8");
  }
  if (existsSync(tsNoCheckPath)) {
    try {
      unlinkSync(tsNoCheckPath);
    } catch {
      // best-effort cleanup
    }
  }
}

process.on("exit", restoreTsconfig);
process.on("SIGINT", () => {
  restoreTsconfig();
  process.exit(130);
});
process.on("SIGTERM", () => {
  restoreTsconfig();
  process.exit(143);
});
process.on("uncaughtException", (error) => {
  restoreTsconfig();
  throw error;
});
process.on("unhandledRejection", (error) => {
  restoreTsconfig();
  throw error;
});

child.on("exit", (code, signal) => {
  restoreTsconfig();
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  if ((code ?? 0) === 0) {
    writeFileSync(buildPathFile, env.NEXT_DIST_DIR, "utf8");
  }
  process.exit(code ?? 0);
});
