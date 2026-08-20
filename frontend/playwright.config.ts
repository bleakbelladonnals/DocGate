import {defineConfig,devices} from "@playwright/test";
import path from "node:path";
const root=path.resolve(__dirname,"..");
export default defineConfig({testDir:"./e2e",fullyParallel:false,workers:1,retries:0,reporter:"list",use:{baseURL:"http://127.0.0.1:3000",trace:"retain-on-failure",...devices["Desktop Chrome"]},webServer:[{command:`${root}/.venv/bin/python ${root}/scripts/seed-e2e.py && DOCGATE_WORKSPACE_ROOT=${root}/test-results/e2e-workspace ${root}/.venv/bin/uvicorn app.main:app --app-dir ${root}/backend --host 127.0.0.1 --port 8765`,url:"http://127.0.0.1:8765/api/v1/health",reuseExistingServer:false,timeout:120000},{command:"npm run dev",url:"http://127.0.0.1:3000/sessions",reuseExistingServer:false,timeout:120000}]});

