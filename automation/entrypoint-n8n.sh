#!/bin/sh
set -e

echo "=== [n8n Pre-Flight] Importing workflow and setting active ==="
n8n import:workflow --input=/automation/workflow.json || true
n8n update:workflow --all --active=true || true

echo "=== [n8n Server] Starting n8n background process ==="
n8n start &
N8N_PID=$!

echo "=== [n8n Health] Waiting for n8n to become healthy ==="
node -e '
const http = require("http");
function checkHealth() {
  http.get("http://127.0.0.1:5678/healthz", (res) => {
    if (res.statusCode === 200) {
      console.log("n8n health check passed (200 OK)");
      process.exit(0);
    } else {
      setTimeout(checkHealth, 1000);
    }
  }).on("error", () => {
    setTimeout(checkHealth, 1000);
  });
}
checkHealth();
'

echo "=== [n8n Owner Setup] Injecting / verifying owner account via REST API ==="
node -e '
const http = require("http");

const email = process.env.N8N_ADMIN_EMAIL || "admin@marketing.local";
const password = process.env.N8N_ADMIN_PASSWORD || "AdminPassword2026!";

function setupOwner() {
  const payload = JSON.stringify({
    email: email,
    firstName: "Admin",
    lastName: "Operator",
    password: password
  });

  const req = http.request("http://127.0.0.1:5678/rest/owner/setup", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(payload)
    }
  }, (res) => {
    let body = "";
    res.on("data", chunk => { body += chunk; });
    res.on("end", () => {
      if (res.statusCode === 200 || res.statusCode === 201) {
        console.log("Owner account created successfully:", res.statusCode);
        process.exit(0);
      } else {
        console.log("Owner setup returned status:", res.statusCode, "- verifying existing login credentials...");
        verifyLogin();
      }
    });
  });

  req.on("error", (err) => {
    console.log("Owner setup error:", err.message);
    process.exit(0);
  });

  req.write(payload);
  req.end();
}

function verifyLogin() {
  const payload = JSON.stringify({
    emailOrLdapLoginId: email,
    password: password
  });

  const req = http.request("http://127.0.0.1:5678/rest/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(payload)
    }
  }, (res) => {
    if (res.statusCode === 200) {
      console.log("Login verified successfully for email:", email);
      process.exit(0);
    } else {
      console.log("Login failed with status:", res.statusCode, "for email:", email);
      process.exit(1);
    }
  });

  req.on("error", () => {
    process.exit(1);
  });

  req.write(payload);
  req.end();
}

setupOwner();
' || {
  echo "=== [n8n Reset] Stale owner database detected. Resetting user state... ==="
  n8n user-management:reset || true
  node -e '
  const http = require("http");
  const payload = JSON.stringify({
    email: process.env.N8N_ADMIN_EMAIL || "admin@marketing.local",
    firstName: "Admin",
    lastName: "Operator",
    password: process.env.N8N_ADMIN_PASSWORD || "AdminPassword2026!"
  });

  const req = http.request("http://127.0.0.1:5678/rest/owner/setup", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(payload)
    }
  }, (res) => {
    let body = "";
    res.on("data", chunk => { body += chunk; });
    res.on("end", () => {
      console.log("Re-created owner account after reset:", res.statusCode);
      process.exit(0);
    });
  });

  req.on("error", () => { process.exit(0); });
  req.write(payload);
  req.end();
  '
}

echo "=== [n8n Container] Binding main process PID $N8N_PID ==="
wait "$N8N_PID"
