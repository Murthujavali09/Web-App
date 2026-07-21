// ======== script.js — Flask + MongoDB Connected Version ========

// ---------- Toast Notification System ----------
let toastContainer = null;

function initToastContainer() {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    toastContainer.id = 'toastContainer';
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

function showToast(message, type = 'info', title = null) {
  initToastContainer();
  
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  // Icons for different types
  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };
  
  const icon = icons[type] || icons.info;
  const displayTitle = title || (type.charAt(0).toUpperCase() + type.slice(1));
  
  toast.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-content">
      <div class="toast-title">${escapeHtml(displayTitle)}</div>
      <div class="toast-message">${escapeHtml(message)}</div>
    </div>
    <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
  `;
  
  // Ensure animation triggers by forcing a reflow
  toastContainer.appendChild(toast);
  // Force reflow to ensure animation plays
  void toast.offsetHeight;
  
  // Auto-remove after 4 seconds for all notification types
  const autoRemoveTime = 4000;
  setTimeout(() => {
    if (toast.parentElement) {
      toast.classList.add('slide-out');
      setTimeout(() => {
        if (toast.parentElement) {
          toast.remove();
        }
      }, 300);
    }
  }, autoRemoveTime);
  
  return toast;
}

// Convenience functions
function showSuccess(message, title = 'Success') {
  return showToast(message, 'success', title);
}

function showError(message, title = 'Error') {
  return showToast(message, 'error', title);
}

function showWarning(message, title = 'Warning') {
  return showToast(message, 'warning', title);
}

function showInfo(message, title = 'Info') {
  return showToast(message, 'info', title);
}

// ---------- Confirmation Dialog ----------
function showConfirmDialog(message, title = 'Confirm Action', type = 'danger') {
  return new Promise((resolve) => {
    // Remove existing confirmation dialog if any
    const existing = document.getElementById('confirmDialogOverlay');
    if (existing) {
      existing.remove();
    }

    const overlay = document.createElement('div');
    overlay.id = 'confirmDialogOverlay';
    overlay.className = 'confirm-dialog-overlay';
    
    const isWarning = type === 'warning';
    const headerClass = isWarning ? 'warning' : '';
    const confirmBtnClass = isWarning ? 'warning' : '';
    const iconClass = isWarning ? 'fa-triangle-exclamation' : 'fa-trash-can';
    const iconBgClass = isWarning ? 'confirm-icon-bg-warning' : 'confirm-icon-bg-danger';
    
    overlay.innerHTML = `
      <div class="confirm-dialog-container">
        <div class="confirm-dialog-header ${headerClass}">
          <div class="confirm-dialog-icon-wrapper ${iconBgClass}">
            <i class="fa-solid ${iconClass} confirm-dialog-icon"></i>
          </div>
          <h3>${escapeHtml(title)}</h3>
        </div>
        <div class="confirm-dialog-body">
          <div class="confirm-dialog-message">${escapeHtml(message)}</div>
          <div class="confirm-dialog-warning">
            <i class="fa-solid fa-exclamation-circle"></i>
            <span>This action cannot be undone.</span>
          </div>
        </div>
        <div class="confirm-dialog-footer">
          <button class="confirm-dialog-btn confirm-dialog-btn-cancel" onclick="closeConfirmDialog(false)">
            <i class="fa-solid fa-xmark"></i>
            Cancel
          </button>
          <button class="confirm-dialog-btn confirm-dialog-btn-confirm ${confirmBtnClass}" onclick="closeConfirmDialog(true)">
            <i class="fa-solid fa-check"></i>
            Confirm
          </button>
        </div>
      </div>
    `;
    
    document.body.appendChild(overlay);
    
    // Show with animation
    requestAnimationFrame(() => {
      overlay.classList.add('show');
    });
    
    // Store resolve function globally so buttons can access it
    window._confirmDialogResolve = resolve;
    
    // Close on overlay click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeConfirmDialog(false);
      }
    });
    
    // Close on Escape key
    const escapeHandler = (e) => {
      if (e.key === 'Escape') {
        closeConfirmDialog(false);
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    document.addEventListener('keydown', escapeHandler);
  });
}

function closeConfirmDialog(confirmed) {
  const overlay = document.getElementById('confirmDialogOverlay');
  if (overlay) {
    overlay.classList.remove('show');
    setTimeout(() => {
      overlay.remove();
    }, 300);
  }
  
  if (window._confirmDialogResolve) {
    window._confirmDialogResolve(confirmed);
    window._confirmDialogResolve = null;
  }
}

// ---------- Utility ----------
function qs(id) { return document.getElementById(id); }
function showMessage(el, text, type = "info") {
  if (!el) return;
  el.textContent = text;
  el.className = `message ${type}`;
  el.style.display = "block";
  setTimeout(() => el.style.display = "none", 3000);
}
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ---------- API Helper ----------
const API_BASE = "/api";

async function apiPut(path, data = {}) {
  const session = loadSession();
  const headers = { "Content-Type": "application/json" };
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  
  const url = API_BASE + path;
  const res = await fetch(url, {
    method: "PUT",
    headers: headers,
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const errorText = await res.text();
    let errorMsg = errorText;
    try {
      const errorJson = JSON.parse(errorText);
      errorMsg = errorJson.error || errorText;
    } catch (e) {
      // Keep original error text
    }
    throw new Error(errorMsg);
  }
  return await res.json();
}

async function apiGet(path, params = {}) {
  const session = loadSession();
  const headers = {};
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  
  const url = new URL(API_BASE + path, window.location.origin);
  Object.keys(params).forEach(k => url.searchParams.append(k, params[k]));
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function apiPost(path, data) {
  const session = loadSession();
  const headers = { "Content-Type": "application/json" };
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(data)
  });
  
  // Get response text first to check if it's empty
  const responseText = await res.text();
  
  if (!res.ok) {
    try {
      const errorJson = JSON.parse(responseText);
      // Extract error message cleanly
      const errorMessage = errorJson.error || errorJson.message || responseText;
      throw new Error(errorMessage);
    } catch (e) {
      // If it's already an Error object with a clean message, rethrow it
      if (e instanceof Error && e.message !== responseText) {
        throw e;
      }
      // Otherwise, try to extract message from raw text
      const cleanMessage = responseText.replace(/^\{.*?"error"\s*:\s*"([^"]+)".*\}$/, '$1');
      throw new Error(cleanMessage !== responseText ? cleanMessage : responseText);
    }
  }
  
  // Handle empty response body (some 201 responses might be empty)
  if (!responseText || responseText.trim() === '') {
    // For successful creation, return a success indicator
    return { success: true, status: res.status };
  }
  
  try {
    return JSON.parse(responseText);
  } catch (e) {
    // If JSON parsing fails but status is ok, return the text or a success indicator
    if (res.status >= 200 && res.status < 300) {
      return { success: true, message: responseText, status: res.status };
    }
    throw new Error(`Invalid response format: ${responseText}`);
  }
}

async function apiDelete(path) {
  const session = loadSession();
  const headers = {};
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  
  const res = await fetch(API_BASE + path, {
    method: "DELETE",
    headers: headers
  });
  if (!res.ok) {
    const errorText = await res.text();
    try {
      const errorJson = JSON.parse(errorText);
      throw new Error(errorJson.error || errorText);
    } catch (e) {
      throw new Error(errorText);
    }
  }
  return await res.json();
}

// ---------- Session ----------
function saveSession(session) {
  localStorage.setItem("BranchPilot_Session", JSON.stringify(session));
}
function loadSession() {
  try { return JSON.parse(localStorage.getItem("BranchPilot_Session")); }
  catch { return null; }
}
function clearSession() {
  localStorage.removeItem("BranchPilot_Session");
}

// ---------- Login ----------
if (qs("loginBtn")) {
  const loginBtn = qs("loginBtn");
  const usernameEl = qs("username");
  const passwordEl = qs("password");
  
  // Function to handle login
  const handleLogin = async () => {
    if (!usernameEl || !passwordEl) {
      console.error("Login form elements not found");
      return;
    }
    const user = usernameEl.value.trim();
    const pass = passwordEl.value;
    const msg = qs("loginMessage");

    if (!user || !pass)
      return showMessage(msg, "Please enter username and password", "error");

    // Try super-admin login first (no IP restriction)
    try {
      const superAdminResult = await apiPost("/managers/super-admin/login", { username: user, password: pass });
      if (superAdminResult && superAdminResult.role === "super-admin") {
        saveSession({ 
          role: "super-admin", 
          name: superAdminResult.name || "Super Admin",
          username: superAdminResult.username || user,
          token: superAdminResult.token
        });
        window.location = "super-admin.html";
        return;
      }
    } catch (superAdminErr) {
      // Super-admin login failed, continue to admin login
    }

    // Try admin login (no IP restriction)
    try {
      const adminResult = await apiPost("/admins/login", { username: user, password: pass });
      if (adminResult && adminResult.role === "admin") {
        saveSession({ 
          role: "admin", 
          name: adminResult.name || "Admin",
          username: adminResult.username || user,
          regions: adminResult.regions || [],
          token: adminResult.token
        });
        window.location = "admin.html";
        return;
      }
    } catch (adminErr) {
      // Admin login failed, continue to manager login
    }

    // Try manager login (no IP restriction)
    try {
      const managerResult = await apiPost("/stores/manager/login", { username: user, password: pass });
      if (managerResult && managerResult.role === "manager") {
        saveSession({ 
          role: "manager", 
          name: managerResult.name || "Manager",
          username: managerResult.username || user,  // Save manager username for filtering stores
          token: managerResult.token
        });
        window.location = "manager.html";
        return;
      }
    } catch (managerErr) {
      // Manager login failed (401 or other error), fall through to store login
    }

    // Try store login (IP restricted)
    try {
      const result = await apiPost("/stores/login", { username: user, password: pass });
      if (result && result.name) {
        saveSession({
          role: "store",
          storeId: result.name,
          storeName: result.name,
          username: user,
          token: result.token
        });
        window.location = "dashboard.html";
        return;
      }
      showMessage(msg, "Login failed. Please try again.", "error");
    } catch (err) {
      let errorMessage = "Invalid credentials";
      if (err && err.message) {
        errorMessage = err.message;
        try {
          const parsed = JSON.parse(errorMessage);
          if (parsed.error) {
            errorMessage = parsed.error;
            if (parsed.details) {
              errorMessage += ` (${parsed.details})`;
            }
          }
        } catch (e) {
          // ignore parsing errors
        }
      }
      showMessage(msg, errorMessage, "error");
    }
  };
  
  // Add click event listener to login button
  loginBtn.addEventListener("click", handleLogin);
  
  // Add Enter key handler for username field
  if (usernameEl) {
    usernameEl.addEventListener("keydown", function(e) {
      if (e.key === "Enter" || e.keyCode === 13) {
        e.preventDefault();
        handleLogin();
      }
    });
  }
  
  // Add Enter key handler for password field
  if (passwordEl) {
    passwordEl.addEventListener("keydown", function(e) {
      if (e.key === "Enter" || e.keyCode === 13) {
        e.preventDefault();
        handleLogin();
      }
    });
  }
  
  // Also handle form submit event
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", function(e) {
      e.preventDefault();
      handleLogin();
    });
  }
}

// ---------- Logout ----------
window.logoutApp = function () {
  clearSession();
  window.location = "login.html";
};

// ---------- Inventory ----------
async function loadInventory(storeId, deviceType = null) {
  const params = { store_id: storeId };
  // Always pass device_type if provided, default to 'metro' if null/undefined
  const typeToUse = deviceType && deviceType.trim() ? deviceType.trim() : 'metro';
  if (typeToUse && typeToUse !== 'all') {
    params.device_type = typeToUse;
  }
  return await apiGet("/inventory/", params);
}

// Helper function to check if at least one employee is clocked in
async function hasClockedInEmployee(storeId) {
  try {
    const data = await apiGet("/timeclock/today", { store_id: storeId });
    if (data.employees && Array.isArray(data.employees)) {
      // Check if any employee has status 'clocked_in' or clock_out is null
      return data.employees.some(emp => emp.status === 'clocked_in' || !emp.clock_out);
    }
    return false;
  } catch (e) {
    console.error('Error checking clocked-in employees:', e);
    // If we can't check, allow submission (fail open)
    return true;
  }
}
async function addInventoryItem(storeId, name, sku, quantity, deviceType = 'metro') {
  return await apiPost("/inventory/", {
    store_id: storeId, name, sku, quantity, device_type: deviceType
  });
}
async function updateInventoryItem(storeId, sku, quantity, itemId = null) {
  const payload = { store_id: storeId, quantity };
  if (itemId) {
    payload._id = itemId;  // Use _id if available for unique identification
  } else {
    payload.sku = sku;  // Fallback to SKU if _id not available
  }
  // Use apiPut to include authentication headers
  return await apiPut("/inventory/", payload);
}

async function updateInventoryItemDetails(storeId, oldSku, name, newSku, itemId = null) {
  const payload = { store_id: storeId, name, new_sku: newSku };
  if (itemId) {
    payload._id = itemId;  // Use _id if available for unique identification
  } else {
    payload.sku = oldSku;  // Fallback to SKU if _id not available
  }
  // Use apiPut to include authentication headers
  return await apiPut("/inventory/", payload);
}
async function deleteInventoryItem(storeId, sku) {
  // Use apiPost with DELETE method to include authentication headers and send data in body
  const session = loadSession();
  const headers = { "Content-Type": "application/json" };
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  const res = await fetch(API_BASE + "/inventory/", {
    method: "DELETE",
    headers: headers,
    body: JSON.stringify({ store_id: storeId, sku })
  });
  if (!res.ok) {
    const errorText = await res.text();
    try {
      const errorJson = JSON.parse(errorText);
      throw new Error(errorJson.error || errorText);
    } catch (e) {
      throw new Error(errorText);
    }
  }
  return await res.json();
}
async function createInventorySnapshot(storeId) {
  // Use device's local time, not UTC
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0'); // getMonth() is 0-indexed
  const day = String(now.getDate()).padStart(2, '0');
  const dateStr = `${year}-${month}-${day}`; // YYYY-MM-DD format in local time
  
  // Also send today's date for comparison
  return await apiPost("/inventory/history/snapshot", {
    store_id: storeId,
    snapshot_date: dateStr,
    today_date: dateStr  // Send today's date from device's local time
  });
}

// ---------- Employees ----------
async function loadEmployees(storeId) {
  return await apiGet("/employees/", { store_id: storeId });
}
async function addEmployee(storeId, name, role) {
  return await apiPost("/employees/", {
    store_id: storeId, name, role
  });
}

// ---------- Timeclock ----------
async function clockIn(employeeId) {
  return await apiPost("/timeclock/clock-in", { employee_id: employeeId });
}
async function clockOut(entryId) {
  return await apiPost("/timeclock/clock-out", { entry_id: entryId });
}

// ---------- EOD ----------
async function submitEod(storeId, reportDate, notes, cashAmount = 0, creditAmount = 0, card1Amount = 0, qpayAmount = 0, boxesCount = 0, 
                        accessoriesAmount = 0, magentaAmount = 0, inventorySold = 0, overShort = 0, total1 = 0,
                        denom100Count = 0, denom100Total = 0, denom50Count = 0, denom50Total = 0,
                        denom20Count = 0, denom20Total = 0, denom10Count = 0, denom10Total = 0,
                        denom5Count = 0, denom5Total = 0, denom1Count = 0, denom1Total = 0, totalBills = 0, submittedBy = null) {
  return await apiPost("/eod/", {
    store_id: storeId,
    report_date: reportDate,
    notes,
    cash_amount: cashAmount,
    credit_amount: creditAmount,
    card1_amount: card1Amount,
    qpay_amount: qpayAmount,
    boxes_count: boxesCount,
    accessories_amount: accessoriesAmount,
    magenta_amount: magentaAmount,
    inventory_sold: inventorySold,
    over_short: overShort,
    total1: total1,
    denom_100_count: denom100Count,
    denom_100_total: denom100Total,
    denom_50_count: denom50Count,
    denom_50_total: denom50Total,
    denom_20_count: denom20Count,
    denom_20_total: denom20Total,
    denom_10_count: denom10Count,
    denom_10_total: denom10Total,
    denom_5_count: denom5Count,
    denom_5_total: denom5Total,
    denom_1_count: denom1Count,
    denom_1_total: denom1Total,
    total_bills: totalBills,
    submitted_by: submittedBy
  });
}
async function loadEods(storeId) {
  return await apiGet("/eod/", { store_id: storeId });
}

// ---------- Stores ----------
async function loadStores(managerUsername = null) {
  const params = managerUsername ? { manager_username: managerUsername } : {};
  return await apiGet("/stores/", params);
}
async function addStore(name, total_boxes, username, password, managerUsername, openingTime, closingTime) {
  return await apiPost("/stores/", { name, total_boxes, username, password, manager_username: managerUsername, opening_time: openingTime, closing_time: closingTime });
}
async function updateStore(name, new_name, total_boxes, username, password, useCurrentIp = false, openingTime = null, closingTime = null) {
  // Use apiPut to include authentication headers
  const payload = { name, new_name, total_boxes, username, password, use_current_ip: useCurrentIp };
  if (openingTime !== null) payload.opening_time = openingTime;
  if (closingTime !== null) payload.closing_time = closingTime;
  return await apiPut("/stores/", payload);
}
async function removeStore(name) {
  // Use apiPost with DELETE method to include authentication headers and send name in body
  const session = loadSession();
  const headers = { "Content-Type": "application/json" };
  if (session?.token) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }
  const res = await fetch(API_BASE + "/stores/", {
    method: "DELETE",
    headers: headers,
    body: JSON.stringify({ name })
  });
  if (!res.ok) {
    const errorText = await res.text();
    try {
      const errorJson = JSON.parse(errorText);
      throw new Error(errorJson.error || errorText);
    } catch (e) {
      throw new Error(errorText);
    }
  }
  return await res.json();
}
// ---------- Helper function for real-time password validation ----------
function setupPasswordValidation(passwordId, confirmPasswordId, errorDivId) {
  const passwordInput = qs(passwordId);
  const confirmPasswordInput = qs(confirmPasswordId);
  const errorDiv = qs(errorDivId);
  
  if (!passwordInput || !confirmPasswordInput || !errorDiv) return;
  
  function validatePasswords() {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    
    if (confirmPassword && password && password !== confirmPassword) {
      errorDiv.textContent = "Passwords do not match";
      errorDiv.classList.remove("hidden");
      confirmPasswordInput.classList.add("border-red-500");
    } else {
      errorDiv.classList.add("hidden");
      confirmPasswordInput.classList.remove("border-red-500");
    }
  }
  
  // Remove existing listeners to avoid duplicates
  const newPasswordInput = passwordInput.cloneNode(true);
  passwordInput.parentNode.replaceChild(newPasswordInput, passwordInput);
  const newConfirmInput = confirmPasswordInput.cloneNode(true);
  confirmPasswordInput.parentNode.replaceChild(newConfirmInput, confirmPasswordInput);
  
  // Re-get elements after cloning
  const newPasswordEl = qs(passwordId);
  const newConfirmEl = qs(confirmPasswordId);
  
  if (newPasswordEl && newConfirmEl) {
    newPasswordEl.addEventListener('input', validatePasswords);
    newConfirmEl.addEventListener('input', validatePasswords);
  }
}

// ---------- Modal Functions (Global - Available Everywhere) ----------
// Modal functions for Edit Item
window.openEditItemModal = function(itemId, sku, name) {
  const modal = qs("editItemModal");
  if (modal) {
    modal.classList.add("show");
    const nameInput = qs("editItemName");
    const skuInput = qs("editItemSku");
    const oldSkuInput = qs("editItemOldSku");
    const itemIdInput = qs("editItemId") || document.createElement("input");
    if (!qs("editItemId")) {
      itemIdInput.type = "hidden";
      itemIdInput.id = "editItemId";
      const form = qs("editItemForm");
      if (form) form.appendChild(itemIdInput);
    }
    if (nameInput) nameInput.value = name || "";
    if (skuInput) skuInput.value = sku || "";
    if (oldSkuInput) oldSkuInput.value = sku || "";
    if (itemIdInput) itemIdInput.value = itemId || "";
    if (nameInput) nameInput.focus();
    hideError("editItemError");
  }
};

window.closeEditItemModal = function() {
  const modal = qs("editItemModal");
  if (modal) {
    modal.classList.remove("show");
  }
};

window.submitEditItem = async function() {
      const session = loadSession();
      if (!session?.storeId) {
        showError("Session expired. Please login again.");
        return;
      }
  
  const nameInput = qs("editItemName");
  const skuInput = qs("editItemSku");
  const oldSkuInput = qs("editItemOldSku");
  const itemIdInput = qs("editItemId");
  const errorDiv = qs("editItemError");
  
  if (!nameInput || !skuInput || !oldSkuInput) return;
  
  const name = nameInput.value.trim();
  const newSku = skuInput.value.trim();
  const oldSku = oldSkuInput.value.trim();
  const itemId = itemIdInput ? itemIdInput.value.trim() : null;
  
  if (!name) {
    showError("editItemError", "Item name is required");
    nameInput.focus();
    return;
  }
  
  if (!newSku) {
    showError("editItemError", "SKU is required");
    skuInput.focus();
    return;
  }
  
  if (!oldSku && !itemId) {
    showError("editItemError", "Error: Original SKU or item ID not found");
    return;
  }
  
  hideError("editItemError");
  
  try {
    await updateInventoryItemDetails(session.storeId, oldSku, name, newSku, itemId);
    
    // Close modal
    closeEditItemModal();
    
    // Show success notification
    showSuccess(`Item "${name}" (SKU: ${newSku}) updated successfully!`, "Item Updated");
    
    // Refresh inventory table
    if (typeof window.renderInventory === 'function') {
      await window.renderInventory();
    } else {
      window.location.reload();
    }
  } catch (e) {
    showError("editItemError", "Failed to update item: " + (e.message || "Unknown error"));
  }
};

// Modal functions for Add Item
window.openAddItemModal = function() {
  console.log("openAddItemModal called");
  const modal = qs("addItemModal");
  console.log("Modal element:", modal);
  if (modal) {
    modal.classList.add("show");
    const nameInput = qs("itemName");
    if (nameInput) {
      nameInput.value = "";
      nameInput.focus();
    }
    const skuInput = qs("itemSku");
    if (skuInput) skuInput.value = "";
    const qtyInput = qs("itemQuantity");
    if (qtyInput) qtyInput.value = "0";
    if (typeof hideError === 'function') {
      hideError("addItemError");
    }
  } else {
    console.error("Modal element with id 'addItemModal' not found!");
  }
};

window.closeAddItemModal = function() {
  const modal = qs("addItemModal");
  if (modal) {
    modal.classList.remove("show");
  }
};

window.submitAddItem = async function() {
      const session = loadSession();
      if (!session?.storeId) {
        showError("Session expired. Please login again.");
        return;
      }
  
  const nameInput = qs("itemName");
  const skuInput = qs("itemSku");
  const qtyInput = qs("itemQuantity");
  const errorDiv = qs("addItemError");
  
  if (!nameInput || !skuInput || !qtyInput) return;
  
  const name = nameInput.value.trim();
  const sku = skuInput.value.trim();
  const quantity = parseInt(qtyInput.value) || 0;
  
  // Get device type from dropdown (default to metro)
  const inventoryTypeSelect = qs("inventoryType");
  const deviceType = inventoryTypeSelect ? inventoryTypeSelect.value : 'metro';
  
  if (!name) {
    showError("addItemError", "Item name is required");
    nameInput.focus();
    return;
  }
  
  if (!sku) {
    showError("addItemError", "SKU is required");
    skuInput.focus();
    return;
  }
  
  hideError("addItemError");
  
  try {
    await addInventoryItem(session.storeId, name, sku, quantity, deviceType);
    
    // Close modal
    window.closeAddItemModal();
    
    // Show success notification
    showSuccess(`Item "${name}" (SKU: ${sku}) added successfully!`, "Item Added");
    
    // Refresh inventory table
    if (typeof window.renderInventory === 'function') {
      await window.renderInventory();
    } else {
      window.location.reload();
    }
  } catch (e) {
    showError("addItemError", "Failed to add item: " + (e.message || "Unknown error"));
  }
};

// Modal functions for Add Store
window.openAddStoreModal = function() {
  const modal = qs("addStoreModal");
  if (modal) {
    modal.classList.add("show");
    const nameInput = qs("storeName");
    const boxesInput = qs("storeTotalBoxes");
    const usernameInput = qs("storeUsername");
    const passwordInput = qs("storePassword");
    const confirmPasswordInput = qs("storeConfirmPassword");
    const addStoreForm = document.getElementById("addStoreForm");
    
    if (nameInput) {
      nameInput.value = "";
      nameInput.focus();
    }
    if (boxesInput) boxesInput.value = "";
    if (usernameInput) usernameInput.value = "";
    if (passwordInput) passwordInput.value = "";
    if (confirmPasswordInput) confirmPasswordInput.value = "";
    hideError("addStoreError");
    // Clear inline password error
    const inlineError = qs("storeConfirmPasswordError");
    if (inlineError) {
      inlineError.classList.add("hidden");
      const confirmInput = qs("storeConfirmPassword");
      if (confirmInput) confirmInput.classList.remove("border-red-500");
    }
    // Setup real-time password validation
    setupPasswordValidation("storePassword", "storeConfirmPassword", "storeConfirmPasswordError");
    
    // Setup Enter key handler - attach to modal element for better scoping and cleanup
    // Remove existing handler if it exists (cleanup from previous open)
    if (modal._addStoreEnterHandler) {
      modal.removeEventListener("keydown", modal._addStoreEnterHandler);
    }
    
    // Create Enter key handler scoped to modal
    modal._addStoreEnterHandler = function(e) {
      // Only trigger if modal is visible
      if (!modal.classList.contains("show")) {
        return;
      }
      
      // Check if Enter key was pressed
      if (e.key === "Enter" || e.keyCode === 13) {
        // Only exclude textarea - allow Enter in all input fields to submit
        const target = e.target;
        if (target && target.tagName === "TEXTAREA") {
          return;
        }
        
        e.preventDefault();
        e.stopPropagation();
        window.submitAddStore();
      }
    };
    
    // Add keydown listener to modal (bubbles from inputs to modal)
    // Use capture phase to catch events before they reach inputs
    modal.addEventListener("keydown", modal._addStoreEnterHandler, true);
  }
};

window.closeAddStoreModal = function() {
  const modal = qs("addStoreModal");
  if (modal) {
    modal.classList.remove("show");
    // Remove Enter key handler when modal closes - guaranteed cleanup
    if (modal._addStoreEnterHandler) {
      modal.removeEventListener("keydown", modal._addStoreEnterHandler, true);
      delete modal._addStoreEnterHandler;
    }
  }
};

window.submitAddStore = async function() {
  const storeNameInput = qs("storeName");
  const boxesInput = qs("storeTotalBoxes");
  const usernameInput = qs("storeUsername");
  const passwordInput = qs("storePassword");
  const confirmPasswordInput = qs("storeConfirmPassword");
  const openingTimeInput = qs("storeOpeningTime");
  const closingTimeInput = qs("storeClosingTime");
  const errorDiv = qs("addStoreError");
  
  if (!storeNameInput || !boxesInput || !usernameInput || !passwordInput || !confirmPasswordInput || !openingTimeInput || !closingTimeInput) return;
  
  const name = storeNameInput.value.trim();
  const totalBoxes = boxesInput.value.trim();
  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const confirmPassword = confirmPasswordInput.value;
  const openingTime = openingTimeInput.value;
  const closingTime = closingTimeInput.value;
  
  // Validation
  if (!name) {
    showError("addStoreError", "Store name is required");
    storeNameInput.focus();
    return;
  }
  
  if (!totalBoxes) {
    showError("addStoreError", "Total boxes is required");
    boxesInput.focus();
    return;
  }
  
  const totalBoxesNum = parseInt(totalBoxes);
  if (isNaN(totalBoxesNum) || totalBoxesNum < 1) {
    showError("addStoreError", "Total boxes must be a positive integer");
    boxesInput.focus();
    return;
  }
  
  if (!username) {
    showError("addStoreError", "Username is required");
    usernameInput.focus();
    return;
  }
  
  if (!password) {
    showError("addStoreError", "Password is required");
    passwordInput.focus();
    return;
  }
  
  if (password !== confirmPassword) {
    const inlineError = qs("storeConfirmPasswordError");
    if (inlineError) {
      inlineError.textContent = "Passwords do not match";
      inlineError.classList.remove("hidden");
      confirmPasswordInput.classList.add("border-red-500");
      confirmPasswordInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    showError("addStoreError", "Passwords do not match");
    confirmPasswordInput.focus();
    return;
  } else {
    // Clear inline error if passwords match
    const inlineError = qs("storeConfirmPasswordError");
    if (inlineError) {
      inlineError.classList.add("hidden");
      confirmPasswordInput.classList.remove("border-red-500");
    }
  }
  
  hideError("addStoreError");
  
  // Get manager username from session
  const session = loadSession();
  if (!session || session.role !== "manager" || !session.username) {
    showError("addStoreError", "Manager session not found. Please login again.");
    return;
  }
  
  if (!openingTime) {
    showError("addStoreError", "Opening time is required");
    openingTimeInput.focus();
    return;
  }
  
  if (!closingTime) {
    showError("addStoreError", "Closing time is required");
    closingTimeInput.focus();
    return;
  }
  
  try {
    const result = await addStore(name, totalBoxesNum, username, password, session.username, openingTime, closingTime);
    
    // Validate result - it should have at least a name or success indicator
    if (!result || (!result.name && !result.success && result.status !== 201)) {
      throw new Error("Invalid response from server");
    }
    
    // Close modal
    closeAddStoreModal();
    
    // Refresh stores list
    const path = window.location.pathname.split("/").pop();
    if (path === "manager.html") {
      if (typeof window.renderStores === 'function') {
        await window.renderStores();
      } else {
        window.location.reload();
      }
    }
    
    const ipNotice = result?.allowed_ip ? ` Allowed IP: ${escapeHtml(result.allowed_ip)}.` : '';
    showSuccess(`Store "${name}" created successfully!${ipNotice}`, "Store Created");
  } catch (e) {
    console.error("Error adding store:", e);
    const errorMsg = e.message || "Unknown error";
    
    // If the error suggests the store might have been created anyway, 
    // refresh and check
    if (errorMsg.includes("timeout") || errorMsg.includes("network") || errorMsg.includes("fetch")) {
      const path = window.location.pathname.split("/").pop();
      if (path === "manager.html" && typeof window.renderStores === 'function') {
        try {
          await window.renderStores();
          // Small delay to ensure render completes
          await new Promise(resolve => setTimeout(resolve, 300));
          const stores = await loadStores(session.username);
          const storeExists = stores.some(store => store.name === name);
          if (storeExists) {
            closeAddStoreModal();
            const createdStore = stores.find(store => store.name === name);
            const ipNotice = createdStore?.allowed_ip 
              ? ` Allowed IP: ${escapeHtml(createdStore.allowed_ip)}.` 
              : '';
            showSuccess(`Store "${name}" created successfully!${ipNotice}`, "Store Created");
            return;
          }
        } catch (refreshError) {
          console.error("Error refreshing stores:", refreshError);
        }
      }
    }
    
    showError("addStoreError", "Failed to add store: " + errorMsg);
  }
};

// Modal functions for Edit Store
window.openEditStoreModal = function(storeName, totalBoxes, username, allowedIp, store = null) {
  const modal = qs("editStoreModal");
  if (modal) {
    modal.classList.add("show");
    const nameInput = qs("editStoreName");
    const originalNameInput = qs("editStoreOriginalName");
    const boxesInput = qs("editStoreTotalBoxes");
    const usernameInput = qs("editStoreUsername");
    const passwordInput = qs("editStorePassword");
    const confirmPasswordInput = qs("editStoreConfirmPassword");
    const openingTimeInput = qs("editStoreOpeningTime");
    const closingTimeInput = qs("editStoreClosingTime");
    const ipInfo = qs("editStoreAllowedIpInfo");
    const updateIpCheckbox = qs("editStoreUseCurrentIp");
    
    if (nameInput) {
      nameInput.value = storeName || "";
      nameInput.focus();
    }
    if (originalNameInput) originalNameInput.value = storeName || "";
    if (boxesInput) boxesInput.value = totalBoxes || "";
    if (usernameInput) usernameInput.value = username || "";
    if (passwordInput) passwordInput.value = "";
    if (confirmPasswordInput) confirmPasswordInput.value = "";
    if (openingTimeInput && store && store.opening_time) openingTimeInput.value = store.opening_time;
    if (closingTimeInput && store && store.closing_time) closingTimeInput.value = store.closing_time;
    if (ipInfo) {
      ipInfo.textContent = `Current allowed IP: ${allowedIp ? escapeHtml(allowedIp) : 'Not set'}`;
    }
    if (updateIpCheckbox) {
      updateIpCheckbox.checked = false;
    }
    hideError("editStoreError");
    // Clear inline password error
    const inlineError = qs("editStoreConfirmPasswordError");
    if (inlineError) {
      inlineError.classList.add("hidden");
      const confirmInput = qs("editStoreConfirmPassword");
      if (confirmInput) confirmInput.classList.remove("border-red-500");
    }
    // Setup real-time password validation
    setupPasswordValidation("editStorePassword", "editStoreConfirmPassword", "editStoreConfirmPasswordError");
  }
};

window.closeEditStoreModal = function() {
  const modal = qs("editStoreModal");
  if (modal) {
    modal.classList.remove("show");
  }
};

window.submitEditStore = async function() {
  const originalNameInput = qs("editStoreOriginalName");
  const nameInput = qs("editStoreName");
  const boxesInput = qs("editStoreTotalBoxes");
  const usernameInput = qs("editStoreUsername");
  const passwordInput = qs("editStorePassword");
  const confirmPasswordInput = qs("editStoreConfirmPassword");
  const openingTimeInput = qs("editStoreOpeningTime");
  const closingTimeInput = qs("editStoreClosingTime");
  const errorDiv = qs("editStoreError");
  const updateIpCheckbox = qs("editStoreUseCurrentIp");
  
  if (!originalNameInput || !nameInput || !boxesInput || !usernameInput || !passwordInput || !confirmPasswordInput || !openingTimeInput || !closingTimeInput) return;
  
  const originalName = originalNameInput.value.trim();
  const newName = nameInput.value.trim();
  const totalBoxes = boxesInput.value.trim();
  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const confirmPassword = confirmPasswordInput.value;
  const openingTime = openingTimeInput.value;
  const closingTime = closingTimeInput.value;
  
  // Validation
  if (!newName) {
    showError("editStoreError", "Store name is required");
    nameInput.focus();
    return;
  }
  
  if (!totalBoxes) {
    showError("editStoreError", "Total boxes is required");
    boxesInput.focus();
    return;
  }
  
  const totalBoxesNum = parseInt(totalBoxes);
  if (isNaN(totalBoxesNum) || totalBoxesNum < 1) {
    showError("editStoreError", "Total boxes must be a positive integer");
    boxesInput.focus();
    return;
  }
  
  if (!username) {
    showError("editStoreError", "Username is required");
    usernameInput.focus();
    return;
  }
  
  if (!password) {
    showError("editStoreError", "Password is required");
    passwordInput.focus();
    return;
  }
  
  if (password !== confirmPassword) {
    const inlineError = qs("editStoreConfirmPasswordError");
    if (inlineError) {
      inlineError.textContent = "Passwords do not match";
      inlineError.classList.remove("hidden");
      confirmPasswordInput.classList.add("border-red-500");
      confirmPasswordInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    showError("editStoreError", "Passwords do not match");
    confirmPasswordInput.focus();
    return;
  } else {
    // Clear inline error if passwords match
    const inlineError = qs("editStoreConfirmPasswordError");
    if (inlineError) {
      inlineError.classList.add("hidden");
      confirmPasswordInput.classList.remove("border-red-500");
    }
  }
  
  hideError("editStoreError");
  
  const useCurrentIp = updateIpCheckbox ? updateIpCheckbox.checked : false;
  
  try {
    await updateStore(originalName, newName, totalBoxesNum, username, password, useCurrentIp);
    
    // Close modal
    closeEditStoreModal();
    
    // Refresh stores list
    const path = window.location.pathname.split("/").pop();
    if (path === "manager.html") {
      if (typeof window.renderStores === 'function') {
        await window.renderStores();
      } else {
        window.location.reload();
      }
    }
    
    const ipMessage = useCurrentIp ? " Allowed IP updated to your current network." : "";
    showSuccess(`Store "${newName}" updated successfully!${ipMessage}`, "Store Updated");
  } catch (e) {
    showError("editStoreError", "Failed to update store: " + (e.message || "Unknown error"));
    console.error("Error updating store:", e);
  }
};

// Helper functions for error display
function showError(elementId, message) {
  const errorDiv = qs(elementId);
  if (errorDiv) {
    errorDiv.textContent = message;
    errorDiv.classList.add("show");
  }
}

function hideError(elementId) {
  const errorDiv = qs(elementId);
  if (errorDiv) {
    errorDiv.textContent = "";
    errorDiv.classList.remove("show");
  }
}

// Close modal when clicking outside
document.addEventListener("click", function(e) {
  if (e.target.classList.contains("modal-overlay")) {
    const modals = document.querySelectorAll(".modal-overlay");
    modals.forEach(modal => modal.classList.remove("show"));
  }
});

function ensureWhatsAppButton() {
  if (document.querySelector(".floating-whatsapp")) return;

  const link = document.createElement("a");
  link.className = "floating-whatsapp";
  link.href = "https://wa.me/917207839129?text=Hi%2C%20I%27m%20interested%20in%20BranchPilot";
  link.target = "_blank";
  link.rel = "noopener";
  link.setAttribute("aria-label", "Chat with us on WhatsApp");
  link.innerHTML = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16.01 3.2c-7.07 0-12.82 5.73-12.82 12.79 0 2.26.6 4.47 1.73 6.41L3.08 29l6.77-1.78a12.8 12.8 0 0 0 6.16 1.57h.01c7.06 0 12.8-5.74 12.8-12.8S23.08 3.2 16.01 3.2Zm0 23.43h-.01a10.6 10.6 0 0 1-5.4-1.48l-.39-.23-4.02 1.06 1.07-3.92-.25-.4a10.57 10.57 0 0 1-1.62-5.67c0-5.85 4.76-10.61 10.62-10.61 2.84 0 5.5 1.1 7.5 3.11a10.55 10.55 0 0 1 3.11 7.5c0 5.86-4.76 10.64-10.61 10.64Zm5.82-7.96c-.32-.16-1.89-.93-2.18-1.04-.29-.1-.5-.16-.71.16-.21.32-.82 1.04-1 1.25-.18.21-.37.24-.69.08-.32-.16-1.35-.5-2.57-1.59-.95-.85-1.59-1.9-1.78-2.22-.18-.32-.02-.49.14-.65.14-.14.32-.37.48-.55.16-.19.21-.32.32-.53.1-.21.05-.4-.03-.56-.08-.16-.71-1.71-.97-2.35-.26-.62-.52-.54-.71-.55h-.61c-.21 0-.56.08-.85.4-.29.32-1.12 1.09-1.12 2.66s1.15 3.09 1.31 3.3c.16.21 2.27 3.46 5.49 4.85.77.33 1.37.53 1.84.68.77.24 1.47.21 2.02.13.62-.09 1.89-.77 2.16-1.52.27-.75.27-1.39.19-1.52-.08-.13-.29-.21-.61-.37Z"/></svg>';
  document.body.appendChild(link);
}

// Close modal on Escape key
document.addEventListener("keydown", function(e) {
  if (e.key === "Escape") {
    const modals = document.querySelectorAll(".modal-overlay");
    modals.forEach(modal => modal.classList.remove("show"));
  }
});

// ---------- Example Page Hooks ----------
document.addEventListener("DOMContentLoaded", async () => {
  ensureWhatsAppButton();

  const session = loadSession();
  const path = window.location.pathname.split("/").pop();

  if (["manager.html", "dashboard.html"].includes(path) && !session)
    window.location = "login.html";

  // General: Hide "Back" button for managers (unless being viewed by super-admin/admin)
  // Also hide/show Alerts tab based on role
  const urlParams = new URLSearchParams(window.location.search);
  const viewAs = urlParams.get('view_as');
  const backToSuperAdmin = qs("backToSuperAdmin");
  const backToSuperAdminMobile = qs("backToSuperAdminMobile");
  const alertsLink = qs("alertsLink");
  
  if (session?.role === "manager" && !viewAs) {
    // Regular manager login - hide back button
    if (backToSuperAdmin) {
      backToSuperAdmin.style.display = "none";
      backToSuperAdmin.classList.add("hidden");
      backToSuperAdmin.classList.remove("md:flex");
    }
    if (backToSuperAdminMobile) {
      backToSuperAdminMobile.style.display = "none";
      backToSuperAdminMobile.classList.add("hidden");
    }
    // Show Alerts tab for managers
    if (alertsLink) {
      alertsLink.style.display = "";
    }
  } else if (session?.role === "super-admin" || session?.role === "admin") {
    // Hide Alerts tab for super-admin/admin
    if (alertsLink) {
      alertsLink.style.display = "none";
    }
  }

  // Dashboard page - Update welcome message with store name
  if (path === "dashboard.html" && session?.role === "store") {
    const dashboardWelcome = qs("dashboardWelcome");
    const storeNameEl = qs("storeName");
    const storeName = session.storeName || session.storeId || "Store";
    if (dashboardWelcome) {
      dashboardWelcome.textContent = `Welcome, ${escapeHtml(storeName)}`;
    }
    if (storeNameEl) {
      storeNameEl.textContent = escapeHtml(storeName);
    }
  }

  // Update store name in header for all store pages
  if (session?.role === "store" && ["dashboard.html", "timeclock.html", "inventory.html", "eod.html"].includes(path)) {
    const storeNameEl = qs("storeName");
    const storeName = session.storeName || session.storeId || "Store";
    if (storeNameEl) {
      storeNameEl.textContent = escapeHtml(storeName);
    }
  }

  // Inventory page
  if (path === "inventory.html" && session?.storeId) {
    const inventoryTableBody = qs("inventoryTableBody");
    const addItemBtn = qs("addItemBtn");
    const inventorySearch = qs("inventorySearch");
    const isManager = session?.role === 'manager';
    
    // Hide Add Item button for employees (only managers can add items)
    if (addItemBtn && !isManager) {
      addItemBtn.style.display = 'none';
    }
    
    window.renderInventory = async function() {
      console.log('=== renderInventory called ===');
      try {
        // Show loading state immediately
        if (inventoryTableBody) {
          inventoryTableBody.innerHTML = `
            <tr>
              <td colspan="4" class="px-6 py-12 text-center">
                <div class="flex flex-col items-center justify-center">
                  <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-blue-600 border-t-transparent mb-3"></div>
                  <p class="text-slate-600 font-medium">Loading inventory...</p>
                </div>
              </td>
            </tr>
          `;
        }
        
        // Get selected device type from dropdown
        const inventoryTypeSelect = qs("inventoryType");
        const selectedDeviceType = inventoryTypeSelect ? inventoryTypeSelect.value : 'metro';
        
        // Ensure we always pass a valid device_type (never null or empty)
        const deviceTypeToUse = selectedDeviceType && selectedDeviceType.trim() ? selectedDeviceType.trim() : 'metro';
        
        console.log('Loading inventory with device_type:', deviceTypeToUse, 'for store:', session.storeId); // Debug log
        const items = await loadInventory(session.storeId, deviceTypeToUse);
        console.log('Loaded items count:', items.length, 'Items:', items.map(i => ({name: i.name, device_type: i.device_type}))); // Debug log
        
        // Load all 3 categories for totals calculation
        const [metroItems, discontinuedItems, unlockedItems] = await Promise.all([
          loadInventory(session.storeId, 'metro'),
          loadInventory(session.storeId, 'discontinued'),
          loadInventory(session.storeId, 'unlocked')
        ]);
        
        // Calculate total devices from all 3 categories
        let totalDevices = 0;
        let totalSims = 0;
        
        const allItems = [...metroItems, ...discontinuedItems, ...unlockedItems];
        allItems.forEach(item => {
          const qty = item.quantity || 0;
          const nameLower = (item.name || '').toLowerCase();
          const skuLower = (item.sku || '').toLowerCase();
          // Check both name and SKU for simcards
          if (nameLower.includes('sim') || nameLower.includes('simcard') || 
              skuLower.includes('sim') || skuLower.includes('simcard')) {
            totalSims += qty;
          } else {
            totalDevices += qty;
          }
        });
        
        // Update totals in footer
        const grandTotalStageEl = qs('grandTotalStage');
        const grandTotalSimsEl = qs('grandTotalSims');
        if (grandTotalStageEl) grandTotalStageEl.textContent = totalDevices;
        if (grandTotalSimsEl) grandTotalSimsEl.textContent = totalSims;
        
        if (!inventoryTableBody) return;
        
        let displayItems = items;
        
        // Filter by search if search term exists
        if (inventorySearch && inventorySearch.value.trim()) {
          const searchTerm = inventorySearch.value.trim().toLowerCase();
          displayItems = items.filter(item => 
            item.name.toLowerCase().includes(searchTerm) || 
            (item.sku && item.sku.toLowerCase().includes(searchTerm))
          );
        }
        
        inventoryTableBody.innerHTML = "";
        
        if (displayItems.length === 0) {
          inventoryTableBody.innerHTML = `<tr><td colspan="4" class="px-6 py-8 text-center text-slate-500">No inventory items found</td></tr>`;
          return;
        }
        
        // Calculate totals for phones and simcards (for current view only - for summary rows)
        let phonesTotal = 0;
        let simcardsTotal = 0;
        
        displayItems.forEach(item => {
          const qty = item.quantity || 0;
          const nameLower = (item.name || '').toLowerCase();
          const skuLower = (item.sku || '').toLowerCase();
          // Check both name and SKU for simcards
          if (nameLower.includes('sim') || nameLower.includes('simcard') || 
              skuLower.includes('sim') || skuLower.includes('simcard')) {
            simcardsTotal += qty;
          } else {
            phonesTotal += qty;
          }
        });
        
        displayItems.forEach(item => {
          const tr = document.createElement("tr");
          tr.className = "hover:bg-blue-50/30 transition-colors";
          tr.style.backgroundColor = "white"; // White background
          const itemId = item._id || item.id || '';  // Use _id if available
          
          // Build row HTML - no Actions column
          const rowHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-900">${escapeHtml(item.name || '')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-600">${escapeHtml(item.sku || '')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-slate-900 font-medium">${item.quantity || 0}</td>
            <td class="px-6 py-4 whitespace-nowrap text-center"><input type="number" class="stage-input w-full px-3 py-2 border border-slate-300 rounded-md text-center bg-white" value="${item.quantity || 0}" data-item-id="${escapeHtml(itemId)}" data-item-sku="${escapeHtml(item.sku || '')}" data-item-name="${escapeHtml(item.name || '')}" /></td>
          `;
          tr.innerHTML = rowHTML;
          inventoryTableBody.appendChild(tr);
        });
        
        // Add phones summary row
        const phonesRow = document.createElement("tr");
        phonesRow.className = "special-row";
        phonesRow.style.background = "white";
        phonesRow.style.fontWeight = "700";
        phonesRow.innerHTML = `
          <td class="px-6 py-4"><strong>phones</strong></td>
          <td class="px-6 py-4">-</td>
          <td class="px-6 py-4 text-center"><strong>${phonesTotal}</strong></td>
          <td class="px-6 py-4 text-center">-</td>
        `;
        inventoryTableBody.appendChild(phonesRow);
        
        // Add simcards summary row
        const simcardsRow = document.createElement("tr");
        simcardsRow.className = "special-row";
        simcardsRow.style.background = "white";
        simcardsRow.style.fontWeight = "700";
        simcardsRow.innerHTML = `
          <td class="px-6 py-4"><strong>simcard</strong></td>
          <td class="px-6 py-4">-</td>
          <td class="px-6 py-4 text-center"><strong>${simcardsTotal}</strong></td>
          <td class="px-6 py-4 text-center">-</td>
        `;
        inventoryTableBody.appendChild(simcardsRow);
      } catch (e) {
        console.error("=== Inventory load failed ===", e);
        console.error("Error details:", e.message, e.stack);
        if (inventoryTableBody) {
          inventoryTableBody.innerHTML = `<tr><td colspan="4" class="px-6 py-8 text-center text-red-600 font-semibold">Failed to load inventory: ${e.message || 'Unknown error'}</td></tr>`;
        }
      }
    }
    
    // Add item button handler
    if (addItemBtn) {
      addItemBtn.addEventListener("click", (e) => {
        e.preventDefault();
        console.log("Add item button clicked");
        if (typeof window.openAddItemModal === 'function') {
          window.openAddItemModal();
        } else {
          console.error("openAddItemModal function not found");
          showError("Modal function not available. Please refresh the page.");
        }
      });
    } else {
      console.error("Add item button not found!");
    }
    
    // Search handler
    if (inventorySearch) {
      inventorySearch.addEventListener("input", () => {
        renderInventory();
      });
    }
    
    // Device type dropdown handler
    const inventoryTypeSelect = qs("inventoryType");
    if (inventoryTypeSelect) {
      inventoryTypeSelect.addEventListener("change", (e) => {
        console.log('Dropdown changed to:', e.target.value);
        if (typeof window.renderInventory === 'function') {
          window.renderInventory();
        } else {
          console.error('renderInventory function not found!');
        }
      });
    } else {
      console.error('inventoryType dropdown not found!');
    }
    
    // Update inventory item
    window.handleUpdateInventoryItem = async function(itemId, sku) {
      // Try to find input by itemId first, then fallback to sku
      let input = null;
      if (itemId) {
        input = document.querySelector(`input[data-item-id="${itemId}"]`);
      }
      if (!input && sku) {
        input = document.querySelector(`input[data-item-sku="${sku}"]`);
      }
      if (!input) return;
      
      const newQuantity = parseInt(input.value) || 0;
      
      try {
        await updateInventoryItem(session.storeId, sku, newQuantity, itemId);
        await renderInventory();
        showSuccess("Inventory updated successfully!");
      } catch (e) {
        showError("Failed to update inventory: " + (e.message || "Unknown error"));
      }
    };
    
    // Edit inventory item (name and SKU)
    window.handleEditInventoryItem = function(itemId, sku, name) {
      openEditItemModal(itemId, sku, name);
    };
    
    // Remove inventory item
    window.handleRemoveInventoryItem = async function(sku, name) {
      const confirmed = await showConfirmDialog(
        `Are you sure you want to remove "${name}" (SKU: ${sku})?`,
        'Remove Inventory Item'
      );
      if (!confirmed) {
        return;
      }
      
      try {
        await deleteInventoryItem(session.storeId, sku);
        await renderInventory();
        showSuccess("Item removed successfully!");
      } catch (e) {
        showError("Failed to remove item: " + (e.message || "Unknown error"));
      }
    };
    
    renderInventory();
    
    // Submit Inventory button handler
    const submitInventoryBtn = qs("submitInventoryBtn");
    if (submitInventoryBtn) {
      window.submitInventorySnapshot = async function() {
        const session = loadSession();
        if (!session?.storeId) {
          showError("Session expired. Please login again.");
          return;
        }
        
        // Check if at least one employee is clocked in
        const hasEmployee = await hasClockedInEmployee(session.storeId);
        if (!hasEmployee) {
          showToast("At least one employee must be clocked in before submitting inventory.", 'error', 'Validation Error');
          return;
        }
        
        try {
          console.log('Submitting inventory snapshot for store:', session.storeId);
          
          // Step 1: Collect all staged quantities from stage-input fields
          const stageInputs = document.querySelectorAll('.stage-input');
          const updates = [];
          
          for (const input of stageInputs) {
            const itemId = input.getAttribute('data-item-id');
            const sku = input.getAttribute('data-item-sku');
            const stagedQuantity = parseInt(input.value) || 0;
            
            if (itemId || sku) {
              updates.push({
                itemId: itemId || null,
                sku: sku || null,
                quantity: stagedQuantity
              });
            }
          }
          
          // Step 2: Update all inventory items with their staged quantities
          console.log(`Updating ${updates.length} inventory items with staged quantities...`);
          const updatePromises = updates.map(update => 
            updateInventoryItem(session.storeId, update.sku, update.quantity, update.itemId)
          );
          
          await Promise.all(updatePromises);
          console.log('All inventory quantities updated successfully');
          
          // Step 3: Refresh the inventory display to show updated quantities
          await renderInventory();
          
          // Step 4: Create snapshot of the updated inventory
          console.log('Creating snapshot for store:', session.storeId);
          const now = new Date();
          const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
          console.log('Snapshot date being sent:', dateStr);
          
          const result = await createInventorySnapshot(session.storeId);
          console.log('Inventory snapshot result:', result);
          
          if (result && (result.message === "Snapshot created" || result.message === "Snapshot updated")) {
            const returnedDate = result.snapshot_date || dateStr;
            console.log('Snapshot created/updated successfully - Sent date:', dateStr, 'Returned date:', returnedDate);
            showSuccess("Inventory quantities updated and snapshot submitted successfully!", "Inventory Submitted");
            
            // Check for inventory mismatch warning
            if (result.warning) {
              console.warn('Inventory mismatch detected:', result.warning);
              showWarning(result.warning, "Inventory Mismatch Warning");
            }
            
            // If we're on the inventory history page, refresh it
            const path = window.location.pathname.split('/').pop();
            if (path === 'store-inventory-history.html' && typeof loadInventoryHistory === 'function') {
              // Small delay to ensure backend has processed the snapshot, then reload
              setTimeout(() => {
                console.log('Refreshing inventory history after snapshot submission...');
                loadInventoryHistory();
              }, 1000); // Increased delay to ensure snapshot is committed
            } else if (path === 'inventory.html') {
              // If on inventory.html, we might want to navigate to history or show a link
              console.log('Snapshot created. Navigate to history page to view it.');
            } else {
              // If not on history page, suggest navigating to it
              console.log('Snapshot created. Navigate to history page to view it.');
            }
          } else {
            console.warn('Unexpected response from snapshot creation:', result);
            showSuccess("Inventory quantities updated and snapshot submitted successfully!", "Inventory Submitted");
          }
        } catch (e) {
          console.error('Error submitting inventory snapshot:', e);
          const errorMsg = e.message || e.error || "Unknown error";
          showError("Failed to submit inventory: " + errorMsg);
        }
      };
    }
  }
  
  // Legacy inventory table (for other pages that might use it)
  if (qs("inventoryTableBody") && session?.storeId && path !== "inventory.html") {
    try {
      const items = await loadInventory(session.storeId);
      const tbody = qs("inventoryTableBody");
      tbody.innerHTML = "";
      items.forEach(it => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${it.name}</td><td>${it.sku}</td><td>${it.quantity}</td>`;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error("Inventory load failed", e);
    }
  }

  // Example: EOD submission page
  if (qs("submitEodBtn") && session?.storeId) {
    qs("submitEodBtn").addEventListener("click", async () => {
      // Get values directly from input elements - support both old and new field IDs
      const cashAmountInput = qs("cashAmount") || qs("cash");
      const creditAmountInput = qs("creditAmount") || qs("card");
      const card1AmountInput = qs("card1");
      const qpayAmountInput = qs("qpayAmount") || qs("qpay");
      const boxesCountInput = qs("boxesCount") || qs("boxes");
      const accessoriesAmountInput = qs("accessories");
      const magentaAmountInput = qs("magenta");
      const inventorySoldInput = qs("inventorySold");
      const overShortInput = qs("overShort");
      const total1Input = qs("total1") || qs("total");
      const eodNotesInput = qs("eodNotes") || qs("comments");
      
      // Denominations
      const denom100CountInput = qs("denom100Count");
      const denom100TotalInput = qs("denom100Total");
      const denom50CountInput = qs("denom50Count");
      const denom50TotalInput = qs("denom50Total");
      const denom20CountInput = qs("denom20Count");
      const denom20TotalInput = qs("denom20Total");
      const denom10CountInput = qs("denom10Count");
      const denom10TotalInput = qs("denom10Total");
      const denom5CountInput = qs("denom5Count");
      const denom5TotalInput = qs("denom5Total");
      const denom1CountInput = qs("denom1Count");
      const denom1TotalInput = qs("denom1Total");
      const totalBillsInput = qs("totalBills");
      
      // Extract and parse values - handle empty strings properly
      const dateStr = new Date().toISOString().split("T")[0];
      const notes = eodNotesInput?.value?.trim() || "";
      
      // Helper to safely parse numeric values
      const parseNumber = (value, parser = parseFloat) => {
        if (!value || value.trim() === "") return 0;
        const parsed = parser(value);
        return isNaN(parsed) ? 0 : parsed;
      };
      
      const cashAmount = cashAmountInput ? parseNumber(cashAmountInput.value, parseFloat) : 0;
      const creditAmount = creditAmountInput ? parseNumber(creditAmountInput.value, parseFloat) : 0;
      const card1Amount = card1AmountInput ? parseNumber(card1AmountInput.value, parseFloat) : 0;
      const qpayAmount = qpayAmountInput ? parseNumber(qpayAmountInput.value, parseFloat) : 0;
      const boxesCount = boxesCountInput ? parseNumber(boxesCountInput.value, parseInt) : 0;
      const accessoriesAmount = accessoriesAmountInput ? parseNumber(accessoriesAmountInput.value, parseFloat) : 0;
      const magentaAmount = magentaAmountInput ? parseNumber(magentaAmountInput.value, parseFloat) : 0;
      const inventorySold = inventorySoldInput ? parseNumber(inventorySoldInput.value, parseInt) : 0;
      
      // Parse over/short - handle formatted values like "+10.50 over" or "5.25 short"
      let overShort = 0;
      if (overShortInput && overShortInput.value) {
        const overShortValue = overShortInput.value.trim();
        // Extract numeric value (remove "over", "short", and "+" sign)
        const numericMatch = overShortValue.match(/([+-]?\d+\.?\d*)/);
        if (numericMatch) {
          let numValue = parseFloat(numericMatch[1]);
          // If it contains "short", make it negative
          if (overShortValue.toLowerCase().includes('short')) {
            numValue = -Math.abs(numValue);
          }
          overShort = numValue;
        }
      }
      const total1 = total1Input ? parseNumber(total1Input.value, parseFloat) : 0;
      
      // Denominations
      const denom100Count = denom100CountInput ? parseNumber(denom100CountInput.value, parseInt) : 0;
      const denom100Total = denom100TotalInput ? parseNumber(denom100TotalInput.value, parseFloat) : 0;
      const denom50Count = denom50CountInput ? parseNumber(denom50CountInput.value, parseInt) : 0;
      const denom50Total = denom50TotalInput ? parseNumber(denom50TotalInput.value, parseFloat) : 0;
      const denom20Count = denom20CountInput ? parseNumber(denom20CountInput.value, parseInt) : 0;
      const denom20Total = denom20TotalInput ? parseNumber(denom20TotalInput.value, parseFloat) : 0;
      const denom10Count = denom10CountInput ? parseNumber(denom10CountInput.value, parseInt) : 0;
      const denom10Total = denom10TotalInput ? parseNumber(denom10TotalInput.value, parseFloat) : 0;
      const denom5Count = denom5CountInput ? parseNumber(denom5CountInput.value, parseInt) : 0;
      const denom5Total = denom5TotalInput ? parseNumber(denom5TotalInput.value, parseFloat) : 0;
      const denom1Count = denom1CountInput ? parseNumber(denom1CountInput.value, parseInt) : 0;
      const denom1Total = denom1TotalInput ? parseNumber(denom1TotalInput.value, parseFloat) : 0;
      const totalBills = totalBillsInput ? parseNumber(totalBillsInput.value, parseFloat) : 0;
      
      const submittedBy = session.name || session.storeName || "Unknown";
      
      // Validation: At least one field must have a value
      const hasAnyValue = cashAmount > 0 || creditAmount > 0 || card1Amount > 0 || qpayAmount > 0 || boxesCount > 0 || 
                          accessoriesAmount > 0 || magentaAmount > 0 || inventorySold > 0 || total1 > 0 || notes.trim().length > 0 ||
                          denom100Count > 0 || denom50Count > 0 || denom20Count > 0 || denom10Count > 0 || 
                          denom5Count > 0 || denom1Count > 0 || totalBills > 0;
      
      if (!hasAnyValue) {
        showToast("Please enter at least one field before submitting.", 'error', 'Validation Error');
        // Focus on the first input field
        if (cashAmountInput) {
          cashAmountInput.focus();
          cashAmountInput.style.borderColor = '#EF4444';
          setTimeout(() => {
            if (cashAmountInput) cashAmountInput.style.borderColor = '';
          }, 3000);
        }
        return;
      }
      
      // Check if at least one employee is clocked in
      const hasEmployee = await hasClockedInEmployee(session.storeId);
      if (!hasEmployee) {
        showToast("At least one employee must be clocked in before submitting EOD.", 'error', 'Validation Error');
        return;
      }
      
      // Debug logging
      console.log("EOD Submission Values:", {
        cashAmount,
        creditAmount,
        card1Amount,
        qpayAmount,
        boxesCount,
        accessoriesAmount,
        magentaAmount,
        inventorySold,
        overShort,
        total1,
        notes,
        dateStr,
        submittedBy,
        denominations: {
          denom100Count, denom100Total,
          denom50Count, denom50Total,
          denom20Count, denom20Total,
          denom10Count, denom10Total,
          denom5Count, denom5Total,
          denom1Count, denom1Total,
          totalBills
        }
      });
      
      try {
        const res = await submitEod(
          session.storeId, dateStr, notes, 
          cashAmount, creditAmount, card1Amount, qpayAmount, boxesCount, 
          accessoriesAmount, magentaAmount, inventorySold, overShort, total1,
          denom100Count, denom100Total, denom50Count, denom50Total,
          denom20Count, denom20Total, denom10Count, denom10Total,
          denom5Count, denom5Total, denom1Count, denom1Total, totalBills,
          submittedBy
        );
        showToast("EOD submitted successfully!", 'success', 'EOD Submitted');
        // Clear form after successful submission
        if (cashAmountInput) cashAmountInput.value = "";
        if (creditAmountInput) creditAmountInput.value = "";
        if (card1AmountInput) card1AmountInput.value = "";
        if (qpayAmountInput) qpayAmountInput.value = "";
        if (total1Input) total1Input.value = "";
        if (boxesCountInput) boxesCountInput.value = "";
        if (accessoriesAmountInput) accessoriesAmountInput.value = "";
        if (magentaAmountInput) magentaAmountInput.value = "";
        if (inventorySoldInput) inventorySoldInput.value = "";
        if (overShortInput) overShortInput.value = "";
        if (eodNotesInput) eodNotesInput.value = "";
        if (denom100CountInput) denom100CountInput.value = "";
        if (denom100TotalInput) denom100TotalInput.value = "";
        if (denom50CountInput) denom50CountInput.value = "";
        if (denom50TotalInput) denom50TotalInput.value = "";
        if (denom20CountInput) denom20CountInput.value = "";
        if (denom20TotalInput) denom20TotalInput.value = "";
        if (denom10CountInput) denom10CountInput.value = "";
        if (denom10TotalInput) denom10TotalInput.value = "";
        if (denom5CountInput) denom5CountInput.value = "";
        if (denom5TotalInput) denom5TotalInput.value = "";
        if (denom1CountInput) denom1CountInput.value = "";
        if (denom1TotalInput) denom1TotalInput.value = "";
        if (totalBillsInput) totalBillsInput.value = "";
      } catch (e) {
        console.error("EOD submit error:", e);
        const errorMsg = e.message || e.error || "Unknown error";
        showToast("EOD submit failed: " + errorMsg, 'error', 'Error');
      }
    });
  }

  // Manager page - Load and display stores (also accessible by super-admin)
  if (path === "manager.html" && (session?.role === "manager" || session?.role === "super-admin" || session?.role === "admin")) {
    const managerCards = qs("managerCards");
    
    // Handle super-admin or admin viewing manager dashboard
    const urlParams = new URLSearchParams(window.location.search);
    const viewAs = urlParams.get('view_as');
    
    // Always hide back to super-admin link by default
    const backLink = qs("backToSuperAdmin");
    if (backLink) backLink.style.display = "none";
    
    // Always hide viewing notice by default
    const notice = qs("viewingAsNotice");
    if (notice) notice.style.display = "none";
    
    if ((session?.role === "super-admin" || session?.role === "admin") && viewAs) {
      // Only show these when super-admin or admin is viewing another manager's dashboard
      // Hide manager-specific navigation for super-admin/admin
      const navLinks = qs("managerNavLinks");
      if (navLinks) navLinks.style.display = "none";
      
      // Show back link only when viewing as another manager
      if (backLink) {
        if (session?.role === "admin") {
          backLink.href = "admin.html";
          backLink.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Admin';
        } else {
          backLink.href = "super-admin.html";
          backLink.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Super Admin';
        }
        backLink.style.display = "flex";
        backLink.classList.remove("hidden");
        backLink.classList.add("md:flex");
      }
      
      // Show mobile back link
      const backLinkMobile = qs("backToSuperAdminMobile");
      if (backLinkMobile) {
        if (session?.role === "admin") {
          backLinkMobile.innerHTML = '<i class="fa-solid fa-arrow-left"></i> Back to Admin';
        } else {
          backLinkMobile.innerHTML = '<i class="fa-solid fa-arrow-left"></i> Back to Super Admin';
        }
        backLinkMobile.classList.remove("hidden");
      }
      
      // Hide add store button for super-admin/admin (they can't add stores for managers)
      const addStoreBtn = qs("addStoreBtn");
      if (addStoreBtn) addStoreBtn.style.display = "none";
      
      // Update title if viewing as another manager
      const title = qs("dashboardTitle");
      if (title) {
        const roleText = session?.role === "admin" ? "Admin" : "Super Admin";
        title.textContent = `Welcome, ${viewAs}`;
        const subtitle = qs("managerSubtitle");
        if (subtitle) {
          subtitle.textContent = `Viewing as ${roleText}`;
        }
      }
      
      if (notice) {
        notice.textContent = `Viewing as: ${viewAs}`;
        notice.style.display = "inline-block";
      }
    } else if (session?.role === "manager") {
      // Regular manager login - ensure back link is hidden
      if (backLink) backLink.style.display = "none";
      if (notice) notice.style.display = "none";
      
      // Show manager name in welcome message
      const title = qs("dashboardTitle");
      if (title) {
        const managerName = session.name || session.username || 'Manager';
        title.textContent = `Welcome, ${managerName}`;
      }
    }
    
    window.renderStores = async function() {
      try {
        // Show loading state immediately
        if (managerCards) {
          managerCards.innerHTML = `
            <div class="flex items-center justify-center py-20">
              <div class="text-center">
                <div class="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent mb-4"></div>
                <p class="text-slate-600 text-lg font-medium">Loading stores...</p>
              </div>
            </div>
          `;
        }
        
        // Check if super-admin is viewing a manager's dashboard
        const urlParams = new URLSearchParams(window.location.search);
        const viewAs = urlParams.get('view_as');
        
        // Get manager username from session and filter stores
        // If super-admin or admin is viewing, use the view_as parameter instead
        let managerUsername = session?.username;
        if ((session?.role === 'super-admin' || session?.role === 'admin') && viewAs) {
          managerUsername = viewAs;
        }
        const stores = await loadStores(managerUsername);
        if (!managerCards) return;
        
        if (stores.length === 0) {
          managerCards.innerHTML = '<div class="text-center py-12 bg-white rounded-xl border border-slate-200 shadow-sm"><p class="text-slate-600 text-lg mb-4">No stores found.</p><p class="text-slate-500">Click "Add Store" to create one.</p></div>';
          return;
        }
        
        // Build query params for navigation (preserve view_as if super-admin or admin)
        const navParams = new URLSearchParams();
        if ((session?.role === 'super-admin' || session?.role === 'admin') && viewAs) {
          navParams.set('view_as', viewAs);
        }
        const navQuery = navParams.toString() ? '&' + navParams.toString() : '';
        
        managerCards.innerHTML = stores.map(store => {
          const escapedName = escapeHtml(store.name);
          const storeId = escapedName;
          const totalBoxes = store.total_boxes || 0;
          const displayName = `${escapedName}-${totalBoxes}`;
          const allowedIp = escapeHtml(store.allowed_ip || 'Not set');
          return `
          <div class="bg-white rounded-xl border-2 border-slate-700 shadow-sm hover:shadow-xl transition-all duration-300 overflow-hidden mb-6" data-store-name="${escapedName}">
            <div class="bg-gradient-to-r from-blue-50 to-slate-50 px-6 py-5 border-b border-slate-200">
              <div class="flex items-center justify-between">
                <div>
                  <h3 class="text-2xl font-bold text-slate-900 mb-1">${displayName}</h3>
                  <div class="text-sm text-slate-600 flex items-center gap-2">
                    <i class="fa-solid fa-network-wired text-xs"></i>
                    <span>Allowed IP: <strong class="text-slate-900">${allowedIp}</strong></span>
                  </div>
                </div>
                <button onclick="window.location='store-inventory.html?store=${encodeURIComponent(escapedName)}${navQuery}'" class="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-slate-700 bg-white border-2 border-slate-300 rounded-lg hover:bg-slate-50 hover:border-slate-400 hover:shadow-lg hover:scale-105 transition-all duration-200">
                  <i class="fa-solid fa-boxes text-slate-600"></i>
                  Manage Inventory
                </button>
              </div>
            </div>
            <div class="store-card-details max-h-0 overflow-hidden transition-all duration-400 ease-in-out" id="details-${storeId.replace(/\s/g, '-')}">
              <div class="p-6 space-y-6">
                <div>
                  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div class="bg-slate-50 p-5 rounded-lg border-l-4 border-blue-600">
                      <div class="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Total Inventory</div>
                      <div class="text-3xl font-bold text-slate-900 mb-1" id="inv-total-${storeId.replace(/\s/g, '-')}">-</div>
                      <div class="text-sm text-slate-500" id="inv-count-${storeId.replace(/\s/g, '-')}">Loading...</div>
                    </div>
                    <div class="bg-slate-50 p-5 rounded-lg border-l-4 border-blue-600 cursor-pointer hover:bg-slate-100 transition-colors" onclick="window.location='store-inventory-history.html?store=${encodeURIComponent(escapedName)}${navQuery}'">
                      <div class="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Inventory History</div>
                      <div class="text-3xl font-bold text-slate-900 mb-1" id="inv-history-${storeId.replace(/\s/g, '-')}">-</div>
                      <div class="text-sm text-slate-500" id="inv-history-detail-${storeId.replace(/\s/g, '-')}">Loading...</div>
                    </div>
                    <div class="bg-emerald-50 p-5 rounded-lg border-l-4 border-emerald-500">
                      <div class="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Employee Activity</div>
                      <div class="text-3xl font-bold text-slate-900 mb-1" id="emp-active-${storeId.replace(/\s/g, '-')}">-</div>
                      <div class="text-sm text-slate-500" id="emp-total-${storeId.replace(/\s/g, '-')}">Loading...</div>
                    </div>
                    <div class="bg-slate-50 p-5 rounded-lg border-l-4 border-blue-600 cursor-pointer hover:bg-slate-100 transition-colors" onclick="window.location='store-eod-list.html?store=${encodeURIComponent(escapedName)}${navQuery}'">
                      <div class="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">EOD Reports</div>
                      <div class="text-3xl font-bold text-slate-900 mb-1" id="eod-total-${storeId.replace(/\s/g, '-')}">-</div>
                      <div class="text-sm text-slate-500" id="eod-latest-${storeId.replace(/\s/g, '-')}">Loading...</div>
                    </div>
                  </div>
                </div>
                <div>
                  <div class="flex items-center gap-3 mb-4">
                    <i class="fa-solid fa-users text-blue-600 text-lg"></i>
                    <h4 class="text-lg font-bold text-slate-900">Employees Today</h4>
                  </div>
                  <div class="space-y-2" id="emp-list-${storeId.replace(/\s/g, '-')}">
                    <div class="text-center py-4 text-slate-500">Loading employees...</div>
                  </div>
                </div>
                <div>
                  <div class="flex items-center gap-3 mb-4">
                    <i class="fa-solid fa-boxes text-blue-600 text-lg"></i>
                    <h4 class="text-lg font-bold text-slate-900">Inventory Preview</h4>
                  </div>
                  <div class="grid grid-cols-2 gap-3" id="inv-grid-${storeId.replace(/\s/g, '-')}">
                    <div class="text-center py-4 text-slate-500">Loading inventory...</div>
                  </div>
                </div>
              </div>
            </div>
            <div class="bg-slate-50 px-6 py-4 border-t border-slate-200 flex flex-wrap items-center justify-center gap-3">
              <button class="manage-store-btn flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-slate-700 bg-white border-2 border-slate-300 rounded-lg hover:bg-slate-50 hover:border-slate-400 hover:shadow-lg hover:scale-105 transition-all duration-200" data-store-name="${escapedName}" onclick="toggleStoreDetails('${escapedName}')">
                <i class="fa-solid fa-chart-bar text-slate-600"></i>
                Manage Store
              </button>
              <button class="btn-edit-store flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-slate-700 bg-white border-2 border-slate-300 rounded-lg hover:bg-slate-50 hover:border-slate-400 hover:shadow-lg hover:scale-105 transition-all duration-200" data-store-name="${escapedName}" data-store-boxes="${totalBoxes}" data-store-username="${escapeHtml(store.username || '')}" data-store-ip="${escapeHtml(store.allowed_ip || '')}" data-store-opening-time="${escapeHtml(store.opening_time || '')}" data-store-closing-time="${escapeHtml(store.closing_time || '')}">
                <i class="fa-solid fa-edit text-slate-600"></i>
                Edit Store
              </button>
              <button class="btn-remove-store flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-slate-700 bg-white border-2 border-slate-300 rounded-lg hover:bg-slate-50 hover:border-slate-400 hover:shadow-lg hover:scale-105 transition-all duration-200" data-store-name="${escapedName}">
                <i class="fa-solid fa-trash text-slate-600"></i>
                Remove Store
              </button>
            </div>
          </div>
        `;
        }).join("");
        
        // Add event listeners
        managerCards.querySelectorAll('.btn-remove-store').forEach(btn => {
          btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const storeName = this.getAttribute('data-store-name');
            handleRemoveStore(storeName);
          });
        });
        
        // Add event listeners for edit store buttons
        managerCards.querySelectorAll('.btn-edit-store').forEach(btn => {
          btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const storeName = this.getAttribute('data-store-name');
            const totalBoxes = parseInt(this.getAttribute('data-store-boxes')) || 0;
            const username = this.getAttribute('data-store-username') || '';
            const allowedIp = this.getAttribute('data-store-ip') || '';
            const openingTime = this.getAttribute('data-store-opening-time') || '';
            const closingTime = this.getAttribute('data-store-closing-time') || '';
            // Find the full store object from the stores array
            const store = stores.find(s => s.name === storeName) || { opening_time: openingTime, closing_time: closingTime };
            handleEditStore(storeName, totalBoxes, username, allowedIp, store);
          });
        });
        
        // Load store details for all stores
        stores.forEach(store => {
          loadStoreDetails(store.name);
        });
      } catch (e) {
        console.error("Failed to load stores", e);
        if (managerCards) {
          managerCards.innerHTML = '<div class="text-center py-12 bg-white rounded-xl border border-red-200 shadow-sm"><p class="text-red-600 text-lg font-semibold mb-2">Failed to load stores</p><p class="text-slate-500">Please refresh the page.</p></div>';
        }
      }
    }
    
    window.handleRemoveStore = async function(storeName) {
      const confirmed = await showConfirmDialog(
        `Are you sure you want to remove the store "${storeName}"?`,
        'Remove Store'
      );
      if (!confirmed) {
        return;
      }
      try {
        await removeStore(storeName);
        await window.renderStores();
      } catch (e) {
        showError("Failed to remove store: " + (e.message || "Unknown error"));
      }
    };
    
    window.handleAddStore = function() {
      window.openAddStoreModal();
    };
    
    window.handleEditStore = function(storeName, totalBoxes, username, allowedIp, store = null) {
      window.openEditStoreModal(storeName, totalBoxes, username, allowedIp, store);
    };
    
    
    // Toggle store details expand/collapse
    window.toggleStoreDetails = function(storeName) {
      const card = document.querySelector(`[data-store-name="${storeName}"]`);
      if (!card) return;
      
      const details = card.querySelector('.store-card-details');
      const btn = card.querySelector('.manage-store-btn');
      
      if (details.classList.contains('expanded')) {
        details.classList.remove('expanded');
        details.style.maxHeight = '0';
        btn.innerHTML = '<i class="fa-solid fa-chart-bar"></i> Manage Store';
      } else {
        details.classList.add('expanded');
        details.style.maxHeight = '3000px';
        btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Hide Details';
        // Load details if not already loaded
        loadStoreDetails(storeName);
      }
    };
    
    // Load store details (employees, inventory, EOD)
    async function loadStoreDetails(storeName) {
      const storeId = storeName;
      const safeId = storeId.replace(/\s/g, '-');
      
      try {
        // Load all data in parallel for better performance
        const [todayDataResult, inventoryResult, historyResult, eodsResult] = await Promise.allSettled([
          apiGet('/timeclock/today', { store_id: storeId }),
          loadInventory(storeId),
          apiGet('/inventory/history', { store_id: storeId }),
          loadEods(storeId)
        ]);
        
        // Process employees data
        try {
          const todayData = todayDataResult.status === 'fulfilled' ? todayDataResult.value : { employees: [] };
          const employees = todayData.employees || [];
          const empList = qs(`emp-list-${safeId}`);
          
          if (empList) {
            if (employees.length === 0) {
              empList.innerHTML = '<div class="text-center py-6 text-slate-500 bg-slate-50 rounded-lg">No employees clocked in today</div>';
            } else {
              empList.innerHTML = employees.map(emp => {
                const status = emp.status === 'clocked_in' ? 'Active' : 'Clocked Out';
                const statusBg = emp.status === 'clocked_in' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600';
                const borderColor = emp.status === 'clocked_in' ? 'border-emerald-500' : 'border-slate-400';
                const hours = emp.hours_worked ? `${emp.hours_worked.toFixed(2)} hrs` : '';
                return `
                  <div class="bg-slate-50 p-4 rounded-lg flex justify-between items-center border-l-4 ${borderColor} hover:bg-slate-100 transition-colors">
                    <div>
                      <div class="font-semibold text-slate-900">${escapeHtml(emp.employee_name)}</div>
                      <div class="text-sm text-slate-600 mt-1">${hours}</div>
                    </div>
                    <span class="px-3 py-1 rounded-full text-xs font-semibold ${statusBg}">${status}</span>
                  </div>
                `;
              }).join('');
            }
            
            const activeCount = employees.filter(e => e.status === 'clocked_in').length;
            qs(`emp-total-${safeId}`).textContent = `${employees.length} today`;
            qs(`emp-active-${safeId}`).textContent = activeCount;
          }
        } catch (err) {
          console.error('Failed to process employees:', err);
          const empList = qs(`emp-list-${safeId}`);
          if (empList) {
            empList.innerHTML = '<div class="text-center py-6 text-red-600 bg-red-50 rounded-lg">Failed to load employees</div>';
          }
        }
        
        // Process inventory data
        try {
          const inventory = inventoryResult.status === 'fulfilled' ? inventoryResult.value : [];
          const invGrid = qs(`inv-grid-${safeId}`);
          if (invGrid) {
            if (inventory.length === 0) {
              invGrid.innerHTML = '<div class="text-center py-6 text-slate-500 bg-slate-50 rounded-lg col-span-full">No inventory items</div>';
            } else {
              // Calculate totals for phones and simcards
              let phonesTotal = 0;
              let simcardsTotal = 0;
              
              inventory.forEach(item => {
                const qty = item.quantity || 0;
                const nameLower = (item.name || '').toLowerCase();
                const skuLower = (item.sku || '').toLowerCase();
                // Check both name and SKU for simcards
                if (nameLower.includes('sim') || nameLower.includes('simcard') || 
                    skuLower.includes('sim') || skuLower.includes('simcard')) {
                  simcardsTotal += qty;
                } else {
                  phonesTotal += qty;
                }
              });
              
              // Display only phones and simcards totals
              invGrid.innerHTML = `
                <div class="bg-white p-4 rounded-lg border border-slate-200 hover:shadow-md transition-shadow">
                  <div class="text-sm font-medium text-slate-900 mb-2">Phones</div>
                  <div class="text-2xl font-bold bg-emerald-100 text-emerald-800 px-3 py-1 rounded-lg text-center">${phonesTotal}</div>
                </div>
                <div class="bg-white p-4 rounded-lg border border-slate-200 hover:shadow-md transition-shadow">
                  <div class="text-sm font-medium text-slate-900 mb-2">Simcards</div>
                  <div class="text-2xl font-bold bg-emerald-100 text-emerald-800 px-3 py-1 rounded-lg text-center">${simcardsTotal}</div>
                </div>
              `;
            }
            const totalQty = inventory.reduce((sum, item) => sum + (item.quantity || 0), 0);
            
            qs(`inv-total-${safeId}`).textContent = totalQty;
            qs(`inv-count-${safeId}`).textContent = `${inventory.length} items`;
          }
        } catch (err) {
          console.error('Failed to process inventory:', err);
        }
        
        // Process inventory history
        try {
          const historyData = historyResult.status === 'fulfilled' ? historyResult.value : [];
          const historyCount = qs(`inv-history-${safeId}`);
          const historyDetail = qs(`inv-history-detail-${safeId}`);
          if (historyCount && historyDetail) {
            historyCount.textContent = historyData.length;
            if (historyData.length > 0) {
              const latest = historyData[0];
              const date = new Date(latest.snapshot_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
              historyDetail.textContent = `Latest: ${date}`;
            } else {
              historyDetail.textContent = 'No snapshots yet';
            }
          }
        } catch (err) {
          console.error('Failed to process inventory history:', err);
          const historyCount = qs(`inv-history-${safeId}`);
          const historyDetail = qs(`inv-history-detail-${safeId}`);
          if (historyCount) historyCount.textContent = '0';
          if (historyDetail) historyDetail.textContent = 'No history';
        }
        
        // Process EOD reports
        try {
          const eods = eodsResult.status === 'fulfilled' ? eodsResult.value : [];
          const eodTotal = qs(`eod-total-${safeId}`);
          const eodLatest = qs(`eod-latest-${safeId}`);
          if (eodTotal && eodLatest) {
            eodTotal.textContent = eods.length;
            if (eods.length > 0) {
              const latest = eods[0];
              const date = new Date(latest.report_date).toLocaleDateString();
              eodLatest.textContent = `Latest: ${date}`;
            } else {
              eodLatest.textContent = 'No reports yet';
            }
          }
        } catch (err) {
          console.error('Failed to process EOD reports:', err);
        }
      } catch (e) {
        console.error(`Failed to load details for ${storeName}:`, e);
      }
    }
    
    window.renderStores();
  }

  // Add Employee nav button for managers: prompt and create employee
  if (path === "manager.html" && session?.role === "manager") {
    const addEmpNav = qs("addEmployeeNavBtn");
    if (addEmpNav) {
      addEmpNav.addEventListener('click', async (e) => {
        e.preventDefault();
        try {
          // Load stores to help the manager choose a valid store id (filtered by manager)
          const managerUsername = session?.username;
          const stores = await loadStores(managerUsername);
          let storeChoice = null;
          if (stores.length === 0) {
            showWarning('No stores found. Please add a store first.');
            return;
          } else if (stores.length === 1) {
            storeChoice = stores[0].name;
          } else {
            const names = stores.map(s => s.name).join(', ');
            storeChoice = prompt(`Enter store name for the employee. Available stores: ${names}`);
            if (!storeChoice) return;
          }

          const empName = prompt('Enter employee name:');
          if (!empName || !empName.trim()) {
            showWarning('Employee name is required');
            return;
          }

          const role = prompt('Enter role (optional):', 'Employee');

          const res = await addEmployee(storeChoice, empName.trim(), role ? role.trim() : null);
          showSuccess('Employee created with ID: ' + (res && res.id ? res.id : JSON.stringify(res)), "Employee Created");
          // Optionally refresh the manager page store details if visible
          if (typeof window.renderStores === 'function') window.renderStores();
        } catch (err) {
          console.error('Add employee failed', err);
          showError('Failed to add employee: ' + (err.message || err));
        }
      });
    }
  }
  
  // Store EOD List page
  if (path === "store-eod-list.html") {
    const session = loadSession();
    if (!session || (session.role !== 'manager' && session.role !== 'super-admin' && session.role !== 'admin')) {
      showError('Access denied. Manager, Admin, or Super Admin login required.');
      window.location = 'login.html';
    }
    
    const eodListContainer = qs("eodListContainer");
    const backBtn = qs("backBtn");
    const storeTitle = qs("storeTitle");
    const backToSuperAdmin = qs("backToSuperAdmin");
    
    // Get store name and view_as from URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const storeName = urlParams.get("store") || "Store";
    const viewAs = urlParams.get("view_as");
    
    // Show "Back to Super Admin" button only if user is super-admin AND view_as is present
    if (backToSuperAdmin) {
      if (viewAs && (session?.role === 'super-admin' || session?.role === 'admin')) {
        if (session?.role === 'admin') {
          backToSuperAdmin.href = "admin.html";
          backToSuperAdmin.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Admin';
        } else {
          backToSuperAdmin.href = "super-admin.html";
          backToSuperAdmin.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Super Admin';
        }
        backToSuperAdmin.classList.remove("hidden");
        backToSuperAdmin.classList.add("md:flex");
      } else {
        backToSuperAdmin.classList.add("hidden");
        backToSuperAdmin.classList.remove("md:flex");
      }
    }
    
    // Update title
    if (storeTitle) {
      storeTitle.innerHTML = `End of Day Reports — <span style="color:#000000;font-weight:bold;">${escapeHtml(storeName)}</span>`;
    }
    
    // Back button handler - preserve view_as if super-admin
    if (backBtn) {
      backBtn.addEventListener("click", () => {
        const backUrl = viewAs ? `manager.html?view_as=${encodeURIComponent(viewAs)}` : 'manager.html';
        window.location = backUrl;
      });
    }
    
    // Load and display EOD reports
    async function loadEODReports() {
      try {
        // Show loading state immediately
        if (eodListContainer) {
          eodListContainer.innerHTML = `
            <div class="flex items-center justify-center py-20">
              <div class="text-center">
                <div class="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent mb-4"></div>
                <p class="text-slate-600 text-lg font-medium">Loading EOD reports...</p>
              </div>
            </div>
          `;
        }
        
        const eods = await loadEods(storeName);
        if (!eodListContainer) return;
        
        if (eods.length === 0) {
          eodListContainer.innerHTML = '<div class="no-data" style="text-align:center;padding:40px;">No EOD reports found for this store.</div>';
          return;
        }
        
        // Normalize dates for comparison
        const normalizeDate = (dateStr) => {
          if (!dateStr) return "";
          const match = dateStr.match(/^(\d{4}-\d{2}-\d{2})/);
          return match ? match[1] : dateStr;
        };
        
        // Group EODs by date and get the latest one for each date
        const eodsByDate = {};
        eods.forEach(eod => {
          const normalizedDate = normalizeDate(eod.report_date);
          if (!normalizedDate) return;
          
          if (!eodsByDate[normalizedDate]) {
            eodsByDate[normalizedDate] = [];
          }
          eodsByDate[normalizedDate].push(eod);
        });
        
        // Sort each group by created_at descending and take the first (latest) one
        const latestEods = [];
        Object.keys(eodsByDate).forEach(date => {
          const dateEods = eodsByDate[date];
          dateEods.sort((a, b) => {
            const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
            const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
            return dateB - dateA; // Descending order (newest first)
          });
          latestEods.push(dateEods[0]); // Take the latest one
        });
        
        // Sort all latest EODs by date descending (newest dates first)
        latestEods.sort((a, b) => {
          const dateA = normalizeDate(a.report_date);
          const dateB = normalizeDate(b.report_date);
          return dateB.localeCompare(dateA); // Descending order
        });
        
        eodListContainer.innerHTML = `
          <div style="display:grid;gap:16px;">
            ${latestEods.map(eod => {
              const date = new Date(eod.report_date).toLocaleDateString('en-US', { 
                month: '2-digit',
                day: '2-digit',
                year: 'numeric'
              });
              const submittedBy = eod.submitted_by || 'Unknown';
              // Parse created_at - if it doesn't have timezone info, treat it as UTC
              let createdAt = eod.created_at ? new Date(eod.created_at) : new Date();
              // If the date string doesn't have timezone info (no Z or +/-), treat it as UTC
              if (eod.created_at && typeof eod.created_at === 'string' && !eod.created_at.match(/[+-]\d{2}:\d{2}|Z$/)) {
                // Treat as UTC by appending 'Z' or creating a UTC date
                createdAt = new Date(eod.created_at + (eod.created_at.endsWith('Z') ? '' : 'Z'));
              }
              let timeStr = 'N/A';
              if (createdAt && !isNaN(createdAt.getTime())) {
                // toLocaleString automatically converts UTC to local timezone
                timeStr = createdAt.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }) + ', ' + createdAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
              }
              const cashAmount = eod.cash_amount || 0;
              const creditAmount = eod.credit_amount || 0;
              const qpayAmount = eod.qpay_amount || 0;
              const totalAmount = cashAmount + creditAmount + qpayAmount;
              
              // Get employee names who worked that day
              const employeesWorked = eod.employees_worked || [];
              const employeesHtml = employeesWorked.length > 0 
                ? `<p style="margin:0 0 6px 0;color:#495057;font-size:0.9rem;"><strong>Employees:</strong> <span style="color:#007bff;">${employeesWorked.map(name => escapeHtml(name)).join(', ')}</span></p>`
                : '';
              
              // Normalize report_date to YYYY-MM-DD format for URL
              const normalizeDateForUrl = (dateStr) => {
                if (!dateStr) return "";
                const match = dateStr.match(/^(\d{4}-\d{2}-\d{2})/);
                return match ? match[1] : dateStr;
              };
              const normalizedDate = normalizeDateForUrl(eod.report_date);
              
              return `
                <div style="background:white;padding:24px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);border:1px solid #e9ecef;cursor:pointer;transition:all 0.2s ease;" 
                     onmouseover="this.style.boxShadow='0 6px 16px rgba(0,0,0,0.15)';this.style.transform='translateY(-2px)'" 
                     onmouseout="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)';this.style.transform='none'"
                     onclick="window.location='store-eod-detail.html?store=${encodeURIComponent(storeName)}&date=${normalizedDate}${viewAs ? '&view_as=' + encodeURIComponent(viewAs) : ''}'">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div style="flex:1;">
                      <h3 style="margin:0 0 12px 0;color:#2c3e50;font-size:1.5rem;font-weight:700;">${date}</h3>
                      <p style="margin:0 0 6px 0;color:#000;font-size:0.9rem;"><strong>Submitted by:</strong> <span style="color:#007bff;font-weight:normal;">${escapeHtml(submittedBy)}</span></p>
                      ${employeesHtml}
                      <p style="margin:6px 0 0 0;color:#6c757d;font-size:0.9rem;">Time: ${timeStr}</p>
                      <p style="margin:12px 0 0 0;color:#6c757d;font-size:0.85rem;font-style:italic;">Click to view details</p>
                    </div>
                    
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `;
      } catch (e) {
        console.error("Failed to load EOD reports", e);
        if (eodListContainer) {
          eodListContainer.innerHTML = '<div class="no-data" style="text-align:center;padding:40px;color:#dc3545;">Failed to load EOD reports. Please try again.</div>';
        }
      }
    }
    
    loadEODReports();
  }
  
  // Store EOD Detail page
  if (path === "store-eod-detail.html") {
    const session = loadSession();
    if (!session || (session.role !== 'manager' && session.role !== 'super-admin' && session.role !== 'admin')) {
      showError('Access denied. Manager, Admin, or Super Admin login required.');
      window.location = 'login.html';
    }
    
    const eodDetailContainer = qs("eodDetailContainer");
    const backToListBtn = qs("backToListBtn");
    const eodDetailTitle = qs("eodDetailTitle");
    const backToSuperAdmin = qs("backToSuperAdmin");
    
    // Get store name, date, and view_as from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const storeName = urlParams.get("store") || "Store";
    const reportDate = urlParams.get("date");
    const viewAs = urlParams.get("view_as");
    
    // Show "Back to Super Admin" button only if user is super-admin AND view_as is present
    if (backToSuperAdmin) {
      if (viewAs && (session?.role === 'super-admin' || session?.role === 'admin')) {
        if (session?.role === 'admin') {
          backToSuperAdmin.href = "admin.html";
          backToSuperAdmin.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Admin';
        } else {
          backToSuperAdmin.href = "super-admin.html";
          backToSuperAdmin.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Super Admin';
        }
        backToSuperAdmin.classList.remove("hidden");
        backToSuperAdmin.classList.add("md:flex");
      } else {
        backToSuperAdmin.classList.add("hidden");
        backToSuperAdmin.classList.remove("md:flex");
      }
    }
    
    // Update title
    if (eodDetailTitle && reportDate) {
      const dateStr = new Date(reportDate).toLocaleDateString('en-US', { 
        month: '2-digit',
        day: '2-digit',
        year: 'numeric'
      });
      eodDetailTitle.textContent = `${storeName} — EOD Report: ${dateStr}`;
    }
    
    // Back button handler - preserve view_as if super-admin
    if (backToListBtn) {
      backToListBtn.addEventListener("click", () => {
        const viewAsParam = viewAs ? `&view_as=${encodeURIComponent(viewAs)}` : '';
        window.location = `store-eod-list.html?store=${encodeURIComponent(storeName)}${viewAsParam}`;
      });
    }
    
    // Load and display EOD report details
    async function loadEODDetail() {
      try {
        // Show loading state immediately
        if (eodDetailContainer) {
          eodDetailContainer.innerHTML = `
            <div class="flex items-center justify-center py-20">
              <div class="text-center">
                <div class="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent mb-4"></div>
                <p class="text-slate-600 text-lg font-medium">Loading EOD report details...</p>
              </div>
            </div>
          `;
        }
        
        const eods = await loadEods(storeName);
        // Normalize dates for comparison - handle both "2025-01-15" and "2025-01-15T00:00:00Z" formats
        const normalizeDate = (dateStr) => {
          if (!dateStr) return "";
          // Extract just the date part (YYYY-MM-DD)
          const match = dateStr.match(/^(\d{4}-\d{2}-\d{2})/);
          return match ? match[1] : dateStr;
        };
        const normalizedReportDate = normalizeDate(reportDate);
        
        // Filter EODs for this date and sort by created_at descending to get the latest one
        const matchingEods = eods.filter(r => {
          const normalizedRDate = normalizeDate(r.report_date);
          return normalizedRDate === normalizedReportDate;
        });
        
        // Sort by created_at descending (newest first) and take the first one
        matchingEods.sort((a, b) => {
          const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
          const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
          return dateB - dateA; // Descending order (newest first)
        });
        
        const eod = matchingEods[0]; // Get the latest EOD for this date
        
        if (!eodDetailContainer) return;
        
        if (!eod) {
          eodDetailContainer.innerHTML = '<div class="no-data" style="text-align:center;padding:40px;color:#dc3545;">EOD report not found.</div>';
          return;
        }
        
        const dateStr = new Date(eod.report_date).toLocaleDateString('en-US', { 
          month: '2-digit',
          day: '2-digit',
          year: 'numeric'
        });
        const submittedBy = eod.submitted_by || 'Unknown';
        // Parse created_at - if it doesn't have timezone info, treat it as UTC
        let createdAt = eod.created_at ? new Date(eod.created_at) : new Date();
        // If the date string doesn't have timezone info (no Z or +/-), treat it as UTC
        if (eod.created_at && typeof eod.created_at === 'string' && !eod.created_at.match(/[+-]\d{2}:\d{2}|Z$/)) {
          // Treat as UTC by appending 'Z'
          createdAt = new Date(eod.created_at + 'Z');
        }
        let timeStr = 'N/A';
        if (createdAt && !isNaN(createdAt.getTime())) {
          // toLocaleString methods automatically convert UTC to local timezone
          timeStr = createdAt.toLocaleDateString('en-GB', { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric'
          }) + ', ' + createdAt.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit', 
            hour12: false
          });
        }
        
        const cashAmount = eod.cash_amount || 0;
        const creditAmount = eod.credit_amount || 0;
        const card1Amount = eod.card1_amount || 0;
        const qpayAmount = eod.qpay_amount || 0;
        const boxesCount = eod.boxes_count || 0;
        const accessoriesAmount = eod.accessories_amount || 0;
        const magentaAmount = eod.magenta_amount || 0;
        const inventorySold = eod.inventory_sold || 0;
        const overShort = eod.over_short || 0;
        const total1 = eod.total1 || 0;
        const total2 = total1 - (cashAmount + creditAmount);
        const notes = eod.notes || 'Normal operations';
        
        // Denominations
        const denom100Count = eod.denom_100_count || 0;
        const denom100Total = eod.denom_100_total || 0;
        const denom50Count = eod.denom_50_count || 0;
        const denom50Total = eod.denom_50_total || 0;
        const denom20Count = eod.denom_20_count || 0;
        const denom20Total = eod.denom_20_total || 0;
        const denom10Count = eod.denom_10_count || 0;
        const denom10Total = eod.denom_10_total || 0;
        const denom5Count = eod.denom_5_count || 0;
        const denom5Total = eod.denom_5_total || 0;
        const denom1Count = eod.denom_1_count || 0;
        const denom1Total = eod.denom_1_total || 0;
        const totalBills = eod.total_bills || 0;
        
        // Determine indicator for total2
        let total2Indicator = '';
        if (total1 === total2) {
          total2Indicator = '<span style="color:#28a745;font-size:1.2rem;margin-left:8px;">✓</span>';
        } else if (total2 > 0) {
          total2Indicator = `<span style="color:#dc3545;font-weight:600;margin-left:8px;">${total2.toFixed(2)} short</span>`;
        } else if (total2 < 0) {
          total2Indicator = `<span style="color:#007bff;font-weight:600;margin-left:8px;">${Math.abs(total2).toFixed(2)} more</span>`;
        }
        
        // Format over/short with color
        let overShortDisplay = '';
        if (overShort > 0) {
          overShortDisplay = `<span style="color:#28a745;font-weight:600;">+₹${overShort.toFixed(2)}</span>`;
        } else if (overShort < 0) {
          overShortDisplay = `<span style="color:#dc3545;font-weight:600;">₹${overShort.toFixed(2)}</span>`;
        } else {
          overShortDisplay = '<span style="color:#6c757d;">₹0.00</span>';
        }
        
        // Build denominations HTML
        let denominationsHtml = '';
        const denominations = [
          { label: '₹100', count: denom100Count, total: denom100Total },
          { label: '₹50', count: denom50Count, total: denom50Total },
          { label: '₹20', count: denom20Count, total: denom20Total },
          { label: '₹10', count: denom10Count, total: denom10Total },
          { label: '₹5', count: denom5Count, total: denom5Total },
          { label: '₹1', count: denom1Count, total: denom1Total }
        ];
        
        const hasDenominations = denominations.some(d => d.count > 0 || d.total > 0) || totalBills > 0;
        
        if (hasDenominations) {
          denominationsHtml = `
            <div style="margin-bottom:32px;">
              <h3 style="margin:0 0 16px 0;color:#2c3e50;font-size:1.2rem;font-weight:700;border-bottom:2px solid #e9ecef;padding-bottom:8px;">Denominations</h3>
              <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:12px;margin-bottom:16px;">
                ${denominations.map(d => `
                  <div style="padding:12px;background:#f8f9fa;border-radius:8px;border:1px solid #dee2e6;">
                    <div style="font-weight:600;color:#495057;margin-bottom:4px;">${d.label}</div>
                    <div style="font-size:0.9rem;color:#6c757d;">Count: ${d.count}</div>
                    <div style="font-size:0.9rem;color:#6c757d;">Total: ₹${d.total.toFixed(2)}</div>
                  </div>
                `).join('')}
              </div>
              ${totalBills > 0 ? `<div style="padding:12px;background:#e7f3ff;border-radius:8px;border:1px solid #b3d9ff;"><strong>Total Bills:</strong> <span style="font-weight:600;color:#0066cc;">₹${totalBills.toFixed(2)}</span></div>` : ''}
            </div>
          `;
        }
        
        eodDetailContainer.innerHTML = `
          <div style="background:white;padding:32px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);border:1px solid #e9ecef;">
            <!-- Report Details Section -->
            <div style="margin-bottom:32px;">
              <h3 style="margin:0 0 16px 0;color:#2c3e50;font-size:1.2rem;font-weight:700;border-bottom:2px solid #e9ecef;padding-bottom:8px;">Report Details</h3>
              <div style="display:grid;gap:12px;">
                <div><strong>Date:</strong> ${dateStr}</div>
                <div><strong>Submitted By:</strong> ${escapeHtml(submittedBy)}</div>
                <div><strong>Submission Time:</strong> ${timeStr}</div>
              </div>
            </div>
            
            <!-- Financial Summary Section -->
            <div style="margin-bottom:32px;">
              <h3 style="margin:0 0 20px 0;color:#2c3e50;font-size:1.3rem;font-weight:700;border-bottom:2px solid #e9ecef;padding-bottom:12px;">Financial Summary</h3>
              <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:20px;">
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #28a745;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Cash</div>
                  <div style="color:#28a745;font-size:1.5rem;font-weight:700;">₹${cashAmount.toFixed(2)}</div>
                </div>
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #007bff;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Card</div>
                  <div style="color:#007bff;font-size:1.5rem;font-weight:700;">₹${creditAmount.toFixed(2)}</div>
                </div>
                ${card1Amount > 0 ? `
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #6f42c1;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Card1</div>
                  <div style="color:#6f42c1;font-size:1.5rem;font-weight:700;">₹${card1Amount.toFixed(2)}</div>
                </div>
                ` : ''}
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #fd7e14;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">QPay</div>
                  <div style="color:#fd7e14;font-size:1.5rem;font-weight:700;">₹${qpayAmount.toFixed(2)}</div>
                </div>
                <div style="padding:16px;background:#e7f3ff;border-radius:8px;border-left:4px solid #0066cc;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Total</div>
                  <div style="color:#0066cc;font-size:1.5rem;font-weight:700;">₹${total1.toFixed(2)}</div>
                </div>
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #6c757d;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Boxes</div>
                  <div style="color:#2c3e50;font-size:1.5rem;font-weight:700;">${boxesCount}</div>
                </div>
                ${accessoriesAmount > 0 ? `
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #17a2b8;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Accessories</div>
                  <div style="color:#17a2b8;font-size:1.5rem;font-weight:700;">₹${accessoriesAmount.toFixed(2)}</div>
                </div>
                ` : ''}
                ${magentaAmount > 0 ? `
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #e83e8c;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Magenta</div>
                  <div style="color:#e83e8c;font-size:1.5rem;font-weight:700;">₹${magentaAmount.toFixed(2)}</div>
                </div>
                ` : ''}
                ${inventorySold > 0 ? `
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #6f42c1;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Inventory Sold</div>
                  <div style="color:#6f42c1;font-size:1.5rem;font-weight:700;">${inventorySold}</div>
                </div>
                ` : ''}
                <div style="padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid ${overShort >= 0 ? '#28a745' : '#dc3545'};">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Over/Short</div>
                  <div style="color:${overShort >= 0 ? '#28a745' : '#dc3545'};font-size:1.5rem;font-weight:700;">${overShort >= 0 ? '+' : ''}₹${overShort.toFixed(2)}</div>
                </div>
                <div style="padding:16px;background:#fff3cd;border-radius:8px;border-left:4px solid #ffc107;">
                  <div style="font-size:0.875rem;color:#6c757d;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">Total2</div>
                  <div style="color:#856404;font-size:1.5rem;font-weight:700;">₹${total2.toFixed(2)}</div>
                  ${total2Indicator}
                </div>
              </div>
            </div>
            
            ${denominationsHtml}
            
            <!-- Notes Section -->
            <div>
              <h3 style="margin:0 0 16px 0;color:#2c3e50;font-size:1.3rem;font-weight:700;border-bottom:2px solid #e9ecef;padding-bottom:12px;">Comments</h3>
              <div style="padding:20px;background:#f8f9fa;border-radius:8px;border:1px solid #dee2e6;min-height:80px;">
                <p style="margin:0;color:#495057;font-size:1rem;line-height:1.6;white-space:pre-wrap;word-wrap:break-word;">${escapeHtml(notes)}</p>
              </div>
            </div>
          </div>
        `;
      } catch (e) {
        console.error("Failed to load EOD detail", e);
        if (eodDetailContainer) {
          eodDetailContainer.innerHTML = '<div class="no-data" style="text-align:center;padding:40px;color:#dc3545;">Failed to load EOD report details. Please try again.</div>';
        }
      }
    }
    
    if (reportDate) {
      loadEODDetail();
    } else {
      if (eodDetailContainer) {
        eodDetailContainer.innerHTML = '<div class="no-data" style="text-align:center;padding:40px;color:#dc3545;">Invalid report date.</div>';
      }
    }
  }
  
  // Store Inventory page (Manager view)
  if (path === "store-inventory.html") {
    const session = loadSession();
    if (!session || (session.role !== 'manager' && session.role !== 'super-admin' && session.role !== 'admin')) {
      showError('Access denied. Manager, Admin, or Super Admin login required.');
      window.location = 'login.html';
    }
    
    const urlParams = new URLSearchParams(window.location.search);
    const storeName = urlParams.get('store') || 'Store';
    const viewAs = urlParams.get('view_as');
    const inventoryTableBody = qs("inventoryTableBody");
    const addItemBtn = qs("addItemBtn");
    const inventorySearch = qs("inventorySearch");
    const storeTitle = qs("storeTitle");
    const backBtn = qs("backBtn");
    const backToSuperAdmin = qs("backToSuperAdmin");
    
    // Show "Back to Super Admin" button only if user is super-admin AND view_as is present
    if (backToSuperAdmin) {
      if (viewAs && (session?.role === 'super-admin' || session?.role === 'admin')) {
        if (session?.role === 'admin') {
          backToSuperAdmin.href = "admin.html";
          backToSuperAdmin.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Admin';
        } else {
          backToSuperAdmin.href = "super-admin.html";
          backToSuperAdmin.innerHTML = '<i class="fa-solid fa-arrow-left mr-2"></i> Back to Super Admin';
        }
        backToSuperAdmin.style.display = "inline-block";
      } else {
        backToSuperAdmin.style.display = "none";
      }
    }
    
    // Update title
    if (storeTitle) {
      storeTitle.textContent = `Inventory Management — ${storeName}`;
    }
    
    // Back button - preserve view_as if super-admin
    if (backBtn) {
      backBtn.addEventListener('click', () => {
        const backUrl = viewAs ? `manager.html?view_as=${encodeURIComponent(viewAs)}` : 'manager.html';
        window.location = backUrl;
      });
    }
    
    window.renderInventory = async function() {
      console.log('=== renderInventory called (store-inventory.html) ===');
      try {
        // Get selected device type from dropdown
        const inventoryTypeSelect = qs("inventoryType");
        const selectedDeviceType = inventoryTypeSelect ? inventoryTypeSelect.value : 'metro';
        const deviceTypeToUse = selectedDeviceType && selectedDeviceType.trim() ? selectedDeviceType.trim() : 'metro';
        
        console.log('Loading inventory with device_type:', deviceTypeToUse, 'for store:', storeName);
        const items = await loadInventory(storeName, deviceTypeToUse);
        console.log('Loaded items count:', items.length, 'Items:', items.map(i => ({name: i.name, device_type: i.device_type})));
        
        // Load all 3 categories for totals calculation
        const [metroItems, discontinuedItems, unlockedItems] = await Promise.all([
          loadInventory(storeName, 'metro'),
          loadInventory(storeName, 'discontinued'),
          loadInventory(storeName, 'unlocked')
        ]);
        
        // Calculate total devices from all 3 categories
        let totalDevices = 0;
        let totalSims = 0;
        
        const allItems = [...metroItems, ...discontinuedItems, ...unlockedItems];
        allItems.forEach(item => {
          const qty = item.quantity || 0;
          const nameLower = (item.name || '').toLowerCase();
          const skuLower = (item.sku || '').toLowerCase();
          // Check both name and SKU for simcards
          if (nameLower.includes('sim') || nameLower.includes('simcard') || 
              skuLower.includes('sim') || skuLower.includes('simcard')) {
            totalSims += qty;
          } else {
            totalDevices += qty;
          }
        });
        
        // Update totals in footer
        const grandTotalStage = qs("grandTotalStage");
        const grandTotalSims = qs("grandTotalSims");
        if (grandTotalStage) grandTotalStage.textContent = totalDevices;
        if (grandTotalSims) grandTotalSims.textContent = totalSims;
        
        if (!inventoryTableBody) return;
        
        let displayItems = items;
        
        // Filter by search if search term exists
        if (inventorySearch && inventorySearch.value.trim()) {
          const searchTerm = inventorySearch.value.trim().toLowerCase();
          displayItems = items.filter(item => 
            item.name.toLowerCase().includes(searchTerm) || 
            (item.sku && item.sku.toLowerCase().includes(searchTerm))
          );
        }
        
        inventoryTableBody.innerHTML = "";
        if (displayItems.length === 0) {
          inventoryTableBody.innerHTML = '<tr><td colspan="5" class="px-6 py-12 text-center text-slate-500 text-sm">No inventory items found</td></tr>';
          return;
        }
        
        // Calculate totals for phones and simcards (for current view only)
        let phonesTotal = 0;
        let simcardsTotal = 0;
        
        displayItems.forEach(item => {
          const qty = item.quantity || 0;
          const nameLower = (item.name || '').toLowerCase();
          const skuLower = (item.sku || '').toLowerCase();
          // Check both name and SKU for simcards
          if (nameLower.includes('sim') || nameLower.includes('simcard') || 
              skuLower.includes('sim') || skuLower.includes('simcard')) {
            simcardsTotal += qty;
          } else {
            phonesTotal += qty;
          }
        });
        
        // Manager view: show Edit and Remove buttons only (light background)
        displayItems.forEach(item => {
          const tr = document.createElement("tr");
          tr.className = "hover:bg-blue-50/30 transition-colors";
          tr.style.backgroundColor = "white"; // White background
          const itemId = item._id || item.id || '';
          tr.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-900">${escapeHtml(item.name || '')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-600">${escapeHtml(item.sku || '')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-slate-900 font-medium">${item.quantity || 0}</td>
            <td class="px-6 py-4 whitespace-nowrap text-center"><input type="number" class="stage-input w-full px-3 py-2 border border-slate-300 rounded-md text-center bg-white" value="${item.quantity || 0}" data-item-id="${escapeHtml(itemId)}" data-item-sku="${escapeHtml(item.sku || '')}" data-item-name="${escapeHtml(item.name || '')}" /></td>
            <td class="px-6 py-4 whitespace-nowrap text-center">
              <div class="flex items-center justify-center gap-2">
                <button onclick="handleEditInventoryItem('${escapeHtml(itemId)}', '${escapeHtml(item.sku || '')}', '${escapeHtml(item.name || '')}')" class="flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-slate-700 bg-white border-2 border-slate-300 rounded-lg hover:bg-slate-50 hover:border-slate-400 hover:shadow-lg hover:scale-105 transition-all duration-200">
                  <i class="fa-solid fa-edit text-slate-600"></i>
                  Edit
                </button>
                <button onclick="handleRemoveInventoryItem('${escapeHtml(item.sku || '')}', '${escapeHtml(item.name || '')}')" class="flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-slate-700 bg-white border-2 border-slate-300 rounded-lg hover:bg-slate-50 hover:border-slate-400 hover:shadow-lg hover:scale-105 transition-all duration-200">
                  <i class="fa-solid fa-trash text-slate-600"></i>
                  Remove
                </button>
              </div>
            </td>
          `;
          inventoryTableBody.appendChild(tr);
        });
        
        // Add phones summary row
        const phonesRow = document.createElement("tr");
        phonesRow.className = "special-row";
        phonesRow.style.background = "white";
        phonesRow.style.fontWeight = "700";
        phonesRow.innerHTML = `
          <td class="px-6 py-4"><strong>phones</strong></td>
          <td class="px-6 py-4">-</td>
          <td class="px-6 py-4 text-center"><strong>${phonesTotal}</strong></td>
          <td class="px-6 py-4 text-center">-</td>
          <td class="px-6 py-4 text-center">-</td>
        `;
        inventoryTableBody.appendChild(phonesRow);
        
        // Add simcards summary row
        const simcardsRow = document.createElement("tr");
        simcardsRow.className = "special-row";
        simcardsRow.style.background = "white";
        simcardsRow.style.fontWeight = "700";
        simcardsRow.innerHTML = `
          <td class="px-6 py-4"><strong>simcard</strong></td>
          <td class="px-6 py-4">-</td>
          <td class="px-6 py-4 text-center"><strong>${simcardsTotal}</strong></td>
          <td class="px-6 py-4 text-center">-</td>
          <td class="px-6 py-4 text-center">-</td>
        `;
        inventoryTableBody.appendChild(simcardsRow);
      } catch (e) {
        console.error("Inventory load failed", e);
        if (inventoryTableBody) {
          inventoryTableBody.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-red-600 font-semibold">Failed to load inventory</td></tr>';
        }
      }
    };
    
    // Save Inventory button handler - stages all changes at once
    window.handleSaveInventory = async function() {
      try {
        // Collect all staged quantities from stage-input fields
        const stageInputs = document.querySelectorAll('.stage-input');
        const updates = [];
        
        for (const input of stageInputs) {
          const itemId = input.getAttribute('data-item-id');
          const sku = input.getAttribute('data-item-sku');
          const stagedQuantity = parseInt(input.value) || 0;
          
          if (itemId && sku) {
            updates.push({
              itemId: itemId,
              sku: sku,
              quantity: stagedQuantity
            });
          }
        }
        
        if (updates.length === 0) {
          showSuccess("No changes to save.", "No Changes");
          return;
        }
        
        // Update all items in parallel
        await Promise.all(updates.map(update => 
          updateInventoryItem(storeName, update.sku, update.quantity, update.itemId)
        ));
        
        // Refresh inventory display
        await renderInventory();
        showSuccess(`Successfully saved ${updates.length} inventory item(s)!`, "Inventory Saved");
      } catch (e) {
        console.error('Error saving inventory:', e);
        const errorMsg = e.message || e.error || "Unknown error";
        showError("Failed to save inventory: " + errorMsg);
      }
    };
    
    // Edit inventory item handler for manager
    window.handleEditInventoryItem = function(itemId, sku, name) {
      openEditItemModal(itemId, sku, name);
    };
    
    // Remove inventory item handler for manager
    window.handleRemoveInventoryItem = async function(sku, name) {
      const confirmed = await showConfirmDialog(
        `Are you sure you want to remove "${name}" (SKU: ${sku})?`,
        'Remove Inventory Item'
      );
      if (!confirmed) {
        return;
      }
      
      try {
        await deleteInventoryItem(storeName, sku);
        await renderInventory();
        showSuccess("Item removed successfully!");
      } catch (e) {
        showError("Failed to remove item: " + (e.message || "Unknown error"));
      }
    };
    
    // Override submitEditItem for manager context
    const originalSubmitEditItem = window.submitEditItem;
    window.submitEditItem = async function() {
      const session = loadSession();
      if (!session || session.role !== 'manager') {
        showError("Session expired. Please login again.");
        return;
      }
  
      const nameInput = qs("editItemName");
      const skuInput = qs("editItemSku");
      const oldSkuInput = qs("editItemOldSku");
      const itemIdInput = qs("editItemId");
      const errorDiv = qs("editItemError");
      
      if (!nameInput || !skuInput || !oldSkuInput) return;
      
      const name = nameInput.value.trim();
      const newSku = skuInput.value.trim();
      const oldSku = oldSkuInput.value.trim();
      const itemId = itemIdInput ? itemIdInput.value.trim() : null;
      
      if (!name) {
        showError("editItemError", "Item name is required");
        nameInput.focus();
        return;
      }
      
      if (!newSku) {
        showError("editItemError", "SKU is required");
        skuInput.focus();
        return;
      }
      
      if (!oldSku && !itemId) {
        showError("editItemError", "Error: Original SKU or item ID not found");
        return;
      }
      
      hideError("editItemError");
      
      try {
        await updateInventoryItemDetails(storeName, oldSku, name, newSku, itemId);
        
        closeEditItemModal();
        
        // Show success notification
        showSuccess(`Item "${name}" (SKU: ${newSku}) updated successfully!`, "Item Updated");
        
        if (typeof window.renderInventory === 'function') {
          await window.renderInventory();
        } else {
          window.location.reload();
        }
      } catch (e) {
        showError("editItemError", "Failed to update item: " + (e.message || "Unknown error"));
      }
    };
    
    // Override submitAddItem for manager context
    const originalSubmitAddItem = window.submitAddItem;
    window.submitAddItem = async function() {
      const session = loadSession();
      if (!session || session.role !== 'manager') {
        showError("Session expired. Please login again.");
        return;
      }
  
      const nameInput = qs("itemName");
      const skuInput = qs("itemSku");
      const qtyInput = qs("itemQuantity");
      const errorDiv = qs("addItemError");
      
      if (!nameInput || !skuInput || !qtyInput) return;
      
      const name = nameInput.value.trim();
      const sku = skuInput.value.trim();
      const quantity = parseInt(qtyInput.value) || 0;
      
      if (!name) {
        showError("addItemError", "Item name is required");
        nameInput.focus();
        return;
      }
      
      if (!sku) {
        showError("addItemError", "SKU is required");
        skuInput.focus();
        return;
      }
      
      hideError("addItemError");
      
      try {
        await addInventoryItem(storeName, name, sku, quantity);
        
        window.closeAddItemModal();
        
        // Show success notification
        showSuccess(`Item "${name}" (SKU: ${sku}) added successfully!`, "Item Added");
        
        if (typeof window.renderInventory === 'function') {
          await window.renderInventory();
        } else {
          window.location.reload();
        }
      } catch (e) {
        showError("addItemError", "Failed to add item: " + (e.message || "Unknown error"));
      }
    };
    
    // Search handler
    if (inventorySearch) {
      inventorySearch.addEventListener("input", () => {
        renderInventory();
      });
    }
    
    // Device type dropdown handler (for store-inventory page)
    const inventoryTypeSelect2 = qs("inventoryType");
    if (inventoryTypeSelect2) {
      inventoryTypeSelect2.addEventListener("change", (e) => {
        console.log('Dropdown changed to:', e.target.value);
        if (typeof window.renderInventory === 'function') {
          window.renderInventory();
        } else {
          console.error('renderInventory function not found!');
        }
      });
    }
    
    // Add item button handler
    if (addItemBtn) {
      addItemBtn.addEventListener("click", (e) => {
        e.preventDefault();
        if (typeof window.openAddItemModal === 'function') {
          window.openAddItemModal();
        }
      });
    }
    
    // Save Inventory button handler
    const saveInventoryBtn = qs("saveInventoryBtn");
    if (saveInventoryBtn) {
      saveInventoryBtn.addEventListener("click", (e) => {
        e.preventDefault();
        if (typeof window.handleSaveInventory === 'function') {
          window.handleSaveInventory();
        }
      });
    }
    
    renderInventory();
  }
});

