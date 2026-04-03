const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

let mainWindow = null;
let rehabProcess = null;
let lastIntakePath = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile("launch.html");
}

function startRehab() {
  if (rehabProcess && !rehabProcess.killed) {
    return;
  }

  const cwd = app.getAppPath();
  const env = { ...process.env };
  if (lastIntakePath) {
    env.REHABSLASH_INTAKE_PATH = lastIntakePath;
  }

  rehabProcess = spawn("python", ["main.py"], {
    cwd,
    stdio: "inherit",
    shell: true,
    env
  });

  rehabProcess.on("exit", () => {
    rehabProcess = null;
    if (mainWindow) {
      try { mainWindow.focus(); } catch (e) {}
    }
  });
}

app.whenReady().then(() => {
  createWindow();

  ipcMain.handle("start-rehab", () => {
    startRehab();
    return true;
  });

  ipcMain.handle("save-intake", async (_evt, intake) => {
    const cwd = app.getAppPath();
    const outDir = path.join(cwd, "data");
    const outPath = path.join(outDir, "intake_latest.json");
    await fs.promises.mkdir(outDir, { recursive: true });
    await fs.promises.writeFile(outPath, JSON.stringify(intake, null, 2), "utf8");
    lastIntakePath = outPath;
    return { ok: true, path: outPath };
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (rehabProcess && !rehabProcess.killed) {
    try { rehabProcess.kill(); } catch (e) {}
  }
  if (process.platform !== "darwin") app.quit();
});
