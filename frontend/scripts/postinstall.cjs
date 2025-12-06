#!/usr/bin/env node

const { execSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const pkgDir = path.join(ROOT, "node_modules", "@nodelib", "fs.stat");
const sentinel = path.join(pkgDir, "out", "index.js");

if (!fs.existsSync(pkgDir)) {
  process.exit(0);
}

if (fs.existsSync(sentinel)) {
  process.exit(0);
}

const tarball = "nodelib-fs.stat-2.0.5.tgz";

try {
  console.log("Hydrating @nodelib/fs.stat (missing compiled files)...");
  execSync(`npm pack @nodelib/fs.stat@2.0.5`, {
    cwd: ROOT,
    stdio: "inherit",
  });
  execSync(
    `tar -xzf ${tarball} -C node_modules/@nodelib/fs.stat --strip-components=1`,
    { cwd: ROOT, stdio: "inherit" },
  );
} catch (err) {
  console.warn("Failed to rehydrate @nodelib/fs.stat:", err.message);
} finally {
  fs.rmSync(path.join(ROOT, tarball), { force: true });
}

