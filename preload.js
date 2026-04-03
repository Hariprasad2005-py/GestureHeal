const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("rehab", {
  start: () => ipcRenderer.invoke("start-rehab"),
  saveIntake: (intake) => ipcRenderer.invoke("save-intake", intake)
});
