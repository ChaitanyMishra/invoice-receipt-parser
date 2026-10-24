const errorMessage = document.querySelector("#error-message");
const loadingMessage = document.querySelector("#loading-message");
const filesBody = document.querySelector("#files-body");
const resultSection = document.querySelector("#result-section");
const invoiceContent = document.querySelector("#invoice-content");
const batchNotice = document.querySelector("#batch-notice");
const authSection = document.querySelector("#auth-section");
const authHeading = document.querySelector("#auth-heading");
const loginForm = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const authToggle = document.querySelector("#auth-toggle");
const mainApp = document.querySelector("#main-app");

// Global variable for the auto-refresh interval
let pollInterval;

// Send all requests through one place so authentication stays consistent.
async function api(path, options = {}) {
  const { responseType, ...requestOptions } = options;
  const headers = new Headers(requestOptions.headers || {});
  const token = localStorage.getItem("token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  requestOptions.headers = headers;

  let response;
  try {
    response = await fetch(path, requestOptions);
  } catch (error) {
    throw new Error(`Network error (no HTTP status): ${error.message}`);
  }

  if (response.status === 401) {
    localStorage.removeItem("token");
    window.location.reload();
    throw new Error("Your session has expired. Please log in again.");
  }

  if (responseType === "blob" && response.ok) {
    return response.blob();
  }

  const responseText = await response.text();
  let data = null;
  if (responseText) {
    try {
      data = JSON.parse(responseText);
    } catch {
      data = responseText;
    }
  }

  if (!response.ok || (data && typeof data === "object" && data.error)) {
    const detail = data && typeof data === "object"
      ? data.detail || data.error || JSON.stringify(data)
      : data;
    throw new Error(`HTTP ${response.status}: ${detail || response.statusText}`);
  }
  return data;
}

async function handleLogin(event) {
  event.preventDefault();
  const credentials = new URLSearchParams(new FormData(loginForm));
  const result = await api("/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: credentials.toString(),
  });
  if (!result || !result.access_token) {
    throw new Error("The login response did not include an access token.");
  }

  localStorage.setItem("token", result.access_token);
  authSection.classList.add("hidden");
  mainApp.classList.remove("hidden");

  // Start auto-refresh on login
  startPolling();
  await loadFiles();
}

async function handleRegister(event) {
  event.preventDefault();
  const formData = new FormData(registerForm);
  await api("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: formData.get("username"),
      password: formData.get("password"),
    }),
  });
  window.alert("Registration successful. Please log in.");
  registerForm.reset();
  showLoginForm();
}

function handleLogout() {
  stopPolling();
  localStorage.removeItem("token");
  window.location.reload();
}

function showLoginForm() {
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
  authHeading.textContent = "Log in";
  authToggle.textContent = "Need an account? Register";
}

// Display request activity and temporarily disable every button.
function setBusy(isBusy) {
  document.querySelectorAll("button").forEach((button) => {
    button.disabled = isBusy;
  });
  loadingMessage.hidden = !isBusy;
}

// Run a UI operation and report request errors in the page.
async function runRequest(operation) {
  setBusy(true);
  errorMessage.hidden = true;
  try {
    await operation();
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
  } finally {
    setBusy(false);
  }
}

// Build a table cell using textContent so API data is never interpreted as markup.
function addCell(row, value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value ?? "—";
  if (className) cell.className = className;
  row.append(cell);
  return cell;
}

// Create a file action button with its request handler.
function actionButton(label, className, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  if (className) button.className = className;
  button.addEventListener("click", () => runRequest(handler));
  return button;
}

// Fetch and render the uploaded file records.
async function loadFiles() {
  const files = await api("/get_upload_data");
  renderFiles(files);
}

// Render the table (separated so polling doesn't trigger the loading spinner)
function renderFiles(files) {
  if (!Array.isArray(files)) {
    throw new Error("The file-list response was not an array.");
  }

  filesBody.replaceChildren();
  if (files.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.className = "empty-state";
    cell.colSpan = 4;
    cell.textContent = "No files uploaded yet.";
    row.append(cell);
    filesBody.append(row);
    return;
  }

  files.forEach((file) => {
    const row = document.createElement("tr");
    addCell(row, file.id);
    addCell(row, file.filename);
    addCell(row, file.status);
    const actions = addCell(row, "", "actions");
    const group = document.createElement("div");
    group.className = "action-group";
    group.append(
      actionButton("Extract", "", () => extractFile(file.id)),
      actionButton("Parse", "", () => parseFile(file.id)),
      actionButton("View", "", () => viewFile(file.id)),
      actionButton("Delete", "delete-button", () => deleteFile(file.id)),
    );
    actions.append(group);
    filesBody.append(row);
  });
}

// Upload one selected file using the backend's `file` multipart field.
async function uploadFile(event) {
  event.preventDefault();
  const input = document.querySelector("#single-file");
  const file = input.files[0];
  if (!file) {
    throw new Error("Choose a file to upload.");
  }

  const formData = new FormData();
  formData.append("file", file);
  const result = await api("/files", { method: "POST", body: formData });
  input.value = "";
  await loadFiles();
  batchNotice.textContent = `Uploaded file #${result.id}: ${result.filename}`;
}

// Upload selected files using the backend's repeated `files` multipart field.
async function uploadBatch(event) {
  event.preventDefault();
  const input = document.querySelector("#batch-files");
  if (input.files.length === 0) {
    throw new Error("Choose at least one file to upload.");
  }

  const formData = new FormData();
  Array.from(input.files).forEach((file) => formData.append("files", file));
  const result = await api("/batch-upload", { method: "POST", body: formData });
  input.value = "";
  await loadFiles();
  batchNotice.textContent =
    `Batch #${result.batch_id} queued (${result.total_files} files).`;
}

// Extract text from a single uploaded file.
async function extractFile(fileId) {
  const result = await api(`/files/${encodeURIComponent(fileId)}/extract`, {
    method: "POST",
  });
  if (result.status === "no_text_extracted") {
    batchNotice.textContent = result.note;
  } else {
    batchNotice.textContent = `Text extracted from file #${fileId}.`;
  }
  await loadFiles();
}

// Parse an uploaded file and display the parsed invoice fields.
async function parseFile(fileId) {
  const result = await api(`/files/${encodeURIComponent(fileId)}/parse`, {
    method: "POST",
  });
  showInvoice(result.parsed_data, fileId);
  await loadFiles(); // Update the table status
}

// Fetch an already parsed invoice from the database (NO re-parsing).
async function viewFile(fileId) {
  try {
    const result = await api(`/files/${encodeURIComponent(fileId)}/invoice`);
    showInvoice(result.parsed_data, fileId);
  } catch (error) {
    if (error.message.includes("404")) {
      throw new Error("This invoice hasn't been parsed yet. Click 'Parse' first.");
    }
    throw error;
  }
}

// Delete a file and refresh the list.
async function deleteFile(fileId) {
  try {
    await api(`/files/${encodeURIComponent(fileId)}`, { method: "DELETE" });
  } catch (error) {
    // If it's a 404, the file is already gone. We can ignore it.
    if (!error.message.includes("404")) {
      throw error;
    }
  }

  // Force a reload of the table
  await loadFiles();

  // Hide the parsed invoice card if it's the one we just deleted
  if (resultSection.dataset.fileId === String(fileId)) {
    resultSection.hidden = true;
  }
}
// Download the server-generated Excel workbook through the shared API helper.
async function downloadInvoices() {
  const button = document.querySelector("#download-excel");
  button.textContent = "Preparing...";
  try {
    const workbook = await api("/invoices/export", {
      method: "GET",
      responseType: "blob",
    });
    const url = URL.createObjectURL(workbook);
    const link = document.createElement("a");
    link.href = url;
    link.download = "invoices.xlsx";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } finally {
    button.textContent = "Download Excel";
  }
}

// Add a text-only invoice field to the result card.
function addInvoiceField(fields, label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value === null || value === undefined || value === ""
    ? "—"
    : String(value);
  wrapper.append(term, description);
  fields.append(wrapper);
}

// Render parsed invoice details and line items without injecting HTML.
function showInvoice(invoice, fileId) {
  if (!invoice || typeof invoice !== "object") {
    throw new Error("The parse response did not include invoice data.");
  }

  const fields = document.createElement("dl");
  fields.className = "invoice-fields";
  [
    ["Vendor", invoice.vendor_name],
    ["GSTIN", invoice.gstin],
    ["Invoice number", invoice.invoice_number],
    ["Date", invoice.date],
    ["Order number", invoice.order_number],
    ["Total", invoice.total],
    ["Address", invoice.address],
  ].forEach(([label, value]) => addInvoiceField(fields, label, value));

  const heading = document.createElement("h3");
  heading.className = "line-items-heading";
  heading.textContent = "Line items";

  const table = document.createElement("table");
  const tableHead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["Description", "Quantity", "Unit price", "Amount"].forEach((label) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    headerRow.append(cell);
  });
  tableHead.append(headerRow);
  table.append(tableHead);

  const tableBody = document.createElement("tbody");
  const items = Array.isArray(invoice.line_items) ? invoice.line_items : [];
  if (items.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.className = "empty-state";
    cell.textContent = "No line items returned.";
    row.append(cell);
    tableBody.append(row);
  } else {
    items.forEach((item) => {
      const row = document.createElement("tr");
      addCell(row, item.description);
      addCell(row, item.quantity);
      addCell(row, item.unit_price);
      addCell(row, item.amount);
      tableBody.append(row);
    });
  }
  table.append(tableBody);

  invoiceContent.replaceChildren(fields, heading, table);
  resultSection.dataset.fileId = String(fileId);
  resultSection.hidden = false;
  resultSection.scrollIntoView({ block: "start" });
}

// Polling functions
function startPolling() {
  stopPolling(); // Clear any existing interval first
  pollInterval = setInterval(async () => {
    // Only poll silently if the app is visible and no request is currently loading
    if (!mainApp.classList.contains("hidden") && loadingMessage.hidden) {
      try {
        const files = await api("/get_upload_data");
        renderFiles(files);
      } catch (e) {
        console.error("Auto-refresh failed:", e);
      }
    }
  }, 5000); // 5 seconds
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// Event Listeners
document.querySelector("#single-upload-form").addEventListener("submit", (event) => {
  runRequest(() => uploadFile(event));
});
document.querySelector("#batch-upload-form").addEventListener("submit", (event) => {
  runRequest(() => uploadBatch(event));
});
document.querySelector("#refresh-files").addEventListener("click", () => {
  runRequest(loadFiles);
});
document.querySelector("#download-excel").addEventListener("click", () => {
  runRequest(downloadInvoices);
});
loginForm.addEventListener("submit", (event) => {
  runRequest(() => handleLogin(event));
});
registerForm.addEventListener("submit", (event) => {
  runRequest(() => handleRegister(event));
});
authToggle.addEventListener("click", () => {
  const showingLogin = !loginForm.classList.contains("hidden");
  if (showingLogin) {
    loginForm.classList.add("hidden");
    registerForm.classList.remove("hidden");
    authHeading.textContent = "Register";
    authToggle.textContent = "Already have an account? Log in";
  } else {
    showLoginForm();
  }
});
document.querySelector("#logout-button").addEventListener("click", handleLogout);

function init() {
  if (localStorage.getItem("token")) {
    authSection.classList.add("hidden");
    mainApp.classList.remove("hidden");

    // Start auto-refresh immediately on page load if logged in
    startPolling();
    runRequest(loadFiles);
    return;
  }

  showLoginForm();
  authSection.classList.remove("hidden");
  mainApp.classList.add("hidden");
}

init();
