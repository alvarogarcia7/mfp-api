// Global state
let sessionId = null;
let currentUser = null;
let localFoodDatabase = [];
let foodEntries = {};
let currentMeal = "snacks";

// DOM elements
const tabNavBtns = document.querySelectorAll(".tab-nav-btn");
const tabContents = document.querySelectorAll(".tab-content");
const statusBadge = document.getElementById("status-badge");
const logoutBtn = document.getElementById("logout-btn");
const foodInstancesList = document.getElementById("food-instances-list");
const foodInstancesCount = document.getElementById("food-instances-count");
const mealSelect = document.getElementById("meal-select");
const foodInput = document.getElementById("food-input");
const searchBtn = document.getElementById("search-btn");
const searchResults = document.getElementById("search-results");
const resultsList = document.getElementById("results-list");
const selectAllBtn = document.getElementById("select-all-btn");
const deselectAllBtn = document.getElementById("deselect-all-btn");
const addAllBtn = document.getElementById("add-all-btn");
const entryDate = document.getElementById("entry-date");
const loadDateBtn = document.getElementById("load-date-btn");
const caloriesSummary = document.getElementById("calorie-summary");

let currentFoodItems = [];
let polarFlowActivities = [];
let selectedPolarActivities = [];

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    // Set today's date as default
    entryDate.valueAsDate = new Date();

    // Check login status
    checkLoginStatus();

    // Event listeners for tabs
    tabNavBtns.forEach(btn => {
        btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    // Login-related event listeners
    setupLoginListeners();

    // Food list event listeners
    mealSelect.addEventListener("change", (e) => {
        currentMeal = e.target.value;
    });
    searchBtn.addEventListener("click", handleSearch);
    foodInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && e.ctrlKey) handleSearch();
    });
    selectAllBtn.addEventListener("click", selectAllResults);
    deselectAllBtn.addEventListener("click", deselectAllResults);
    addAllBtn.addEventListener("click", addAllSelected);
    logoutBtn.addEventListener("click", handleLogout);
    loadDateBtn.addEventListener("click", loadFoodEntries);

    // Login sub-tabs
    document.querySelectorAll("[data-subtab]").forEach(btn => {
        btn.addEventListener("click", () => switchLoginTab(btn.dataset.subtab));
    });

    // Polar Flow event listeners
    const polarStartDate = document.getElementById("polar-start-date");
    const polarEndDate = document.getElementById("polar-end-date");
    const polarQuick1Week = document.getElementById("polar-quick-1-week");
    const polarQuick1Month = document.getElementById("polar-quick-1-month");
    const polarFetchBtn = document.getElementById("polar-fetch-btn");
    const polarSyncBtn = document.getElementById("polar-sync-btn");

    if (polarStartDate) polarStartDate.valueAsDate = new Date();
    if (polarEndDate) polarEndDate.valueAsDate = new Date();

    if (polarQuick1Week) polarQuick1Week.addEventListener("click", setPolarQuick1Week);
    if (polarQuick1Month) polarQuick1Month.addEventListener("click", setPolarQuick1Month);
    if (polarFetchBtn) polarFetchBtn.addEventListener("click", fetchPolarActivities);
    if (polarSyncBtn) polarSyncBtn.addEventListener("click", syncPolarTMFP);

    // Load food instances on startup
    loadFoodInstances();
    checkPolarFlowStatus();
});

async function checkLoginStatus() {
    try {
        console.log("🔐 Checking login status...");
        const response = await fetch("/api/status");
        const data = await response.json();

        if (data.logged_in) {
            currentUser = data.username;
            console.log("✅ Logged in as:", currentUser);
            updateStatusBadge("online");
            logoutBtn.style.display = "block";
            caloriesSummary.style.display = "block";

            // Try to load stored session ID
            sessionId = localStorage.getItem("sessionId");
            loadFoodEntries();
        } else {
            console.log("📴 Offline mode");
            updateStatusBadge("offline");
            logoutBtn.style.display = "none";
            caloriesSummary.style.display = "none";
            // Load local entries if available
            loadFoodEntries();
        }
    } catch (err) {
        console.error("Error checking login status:", err);
        updateStatusBadge("offline");
    }
}

function updateStatusBadge(status) {
    statusBadge.className = `status-badge ${status}`;
    statusBadge.textContent = status === "online" ? "Online" : "Offline";
}

function switchTab(tabName) {
    tabNavBtns.forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    tabContents.forEach(content => {
        const contentTab = content.id.replace("-tab", "");
        if (contentTab === tabName) {
            content.classList.add("active");
            // Load data for this tab
            if (tabName === "food-instances") {
                loadFoodInstances();
            } else if (tabName === "food-entries") {
                loadFoodEntries();
            }
        } else {
            content.classList.remove("active");
        }
    });
}

function switchLoginTab(tabName) {
    document.querySelectorAll("[data-subtab]").forEach(btn => {
        if (btn.dataset.subtab === tabName) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    document.querySelectorAll(".login-tab").forEach(form => {
        if (form.dataset.subtab === tabName) {
            form.classList.add("active");
        } else {
            form.classList.remove("active");
        }
    });
}

async function loadFoodInstances() {
    try {
        console.log("📚 Loading food instances...");
        foodInstancesList.innerHTML = '<div class="loading">Loading...</div>';

        const response = await fetch("/api/food-instances");
        const data = await response.json();

        localFoodDatabase = data.foods || [];
        console.log(`✅ Loaded ${localFoodDatabase.length} foods`);

        displayFoodInstances(localFoodDatabase);
        foodInstancesCount.textContent = `Total: ${localFoodDatabase.length} foods`;
    } catch (err) {
        console.error("❌ Error loading foods:", err);
        foodInstancesList.innerHTML = '<div class="error">Error loading food database</div>';
    }
}

function displayFoodInstances(foods) {
    foodInstancesList.innerHTML = "";

    if (foods.length === 0) {
        foodInstancesList.innerHTML = '<div class="empty-state">No foods in database. Add foods in the "Today\'s Entries" tab.</div>';
        return;
    }

    foods.forEach(food => {
        const item = document.createElement("div");
        item.className = "food-item";
        item.innerHTML = `
            <div class="food-item-name">${escapeHtml(food.name)}</div>
            <div class="food-item-meta">
                ${food.measurement ? `<div>📏 ${food.measurement.value}${food.measurement.unit}</div>` : ''}
                <div>🔥 ${Math.round(food.calories)} cal</div>
            </div>
            <div class="food-item-nutrition">
                <div class="nutrition-stat">Protein: <span class="nutrition-value">${food.protein ? Math.round(food.protein) + 'g' : '-'}</span></div>
                <div class="nutrition-stat">Carbs: <span class="nutrition-value">${food.carbs ? Math.round(food.carbs) + 'g' : '-'}</span></div>
                <div class="nutrition-stat">Fat: <span class="nutrition-value">${food.fat ? Math.round(food.fat) + 'g' : '-'}</span></div>
                <div class="nutrition-stat">Fiber: <span class="nutrition-value">${food.fiber ? Math.round(food.fiber) + 'g' : '-'}</span></div>
            </div>
        `;
        foodInstancesList.appendChild(item);
    });
}

async function loadFoodEntries() {
    try {
        const dateStr = entryDate.value;
        console.log(`📥 Loading entries for ${dateStr}...`);

        if (sessionId) {
            const response = await fetch(`/api/food-entries?date_str=${dateStr}`, {
                headers: { "Authorization": `Bearer ${sessionId}` }
            });
            const data = await response.json();
            foodEntries = data.meals || {};
        }

        displayFoodEntries(foodEntries);
    } catch (err) {
        console.warn("Note: Food entries not available online, using local cache");
        displayFoodEntries({});
    }
}

function displayFoodEntries(meals) {
    ["breakfast", "lunch", "dinner", "snacks"].forEach(meal => {
        const entries = meals[meal] || [];
        const entryList = document.getElementById(`${meal}-entries`);
        entryList.innerHTML = "";

        if (entries.length === 0) {
            entryList.innerHTML = '<li class="empty-state">No entries</li>';
        } else {
            entries.forEach(entry => {
                const li = document.createElement("li");
                li.innerHTML = `
                    <span class="entry-name">${escapeHtml(entry.name || "Food")}</span>
                    <span class="entry-calories">${Math.round(entry.calories || 0)} cal</span>
                `;
                entryList.appendChild(li);
            });
        }
    });
}

function handleSearch() {
    const text = foodInput.value.trim();
    if (!text) return;

    const lines = text.split('\n').map(l => l.trim()).filter(l => l);
    if (lines.length === 0) return;

    console.log("🔍 Searching local database...");
    currentFoodItems = [];

    for (const line of lines) {
        const parsed = parseInput(line);
        const results = localFoodDatabase.filter(food =>
            food.name.toLowerCase().includes(parsed.name.toLowerCase())
        ).slice(0, 5);

        if (results.length > 0) {
            console.log(`✅ Found ${results.length} results for ${parsed.name}`);
            currentFoodItems.push({
                query: line,
                parsed: parsed,
                results: results,
                selected: results[0]
            });
        } else {
            alert(`"${parsed.name}" not found in local database.\n\nAdd it in MyFitnessPal and sync here.`);
        }
    }

    if (currentFoodItems.length > 0) {
        showResults();
    }
}

function showResults() {
    resultsList.innerHTML = "";

    currentFoodItems.forEach((item, itemIdx) => {
        const itemDiv = document.createElement("div");
        itemDiv.style.marginBottom = "20px";
        itemDiv.style.paddingBottom = "20px";
        itemDiv.style.borderBottom = "1px solid #eee";

        const header = document.createElement("div");
        header.style.fontWeight = "600";
        header.style.marginBottom = "10px";
        header.textContent = `${item.query}`;
        itemDiv.appendChild(header);

        const resultsDiv = document.createElement("div");
        resultsDiv.style.display = "flex";
        resultsDiv.style.flexDirection = "column";
        resultsDiv.style.gap = "8px";

        item.results.forEach((food, foodIdx) => {
            const div = document.createElement("div");
            div.className = "result-item";
            if (foodIdx === 0) div.classList.add("pre-selected");

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = (foodIdx === 0);
            checkbox.dataset.itemIdx = itemIdx;
            checkbox.dataset.foodIdx = foodIdx;
            checkbox.addEventListener("change", (e) => {
                if (e.target.checked) {
                    item.selected = food;
                    resultsList.querySelectorAll(`input[data-itemIdx="${itemIdx}"]`).forEach(cb => {
                        if (cb !== checkbox) cb.checked = false;
                    });
                }
            });

            const content = document.createElement("div");
            content.className = "result-content";
            const calories = Math.round(food.calories || 0);
            content.innerHTML = `
                <div class="result-name">${escapeHtml(food.name)}</div>
                <div class="result-meta">
                    <span>${calories} cal</span>
                    <span>P: ${food.protein ? Math.round(food.protein) : '?'}g</span>
                    <span>C: ${food.carbs ? Math.round(food.carbs) : '?'}g</span>
                    <span>F: ${food.fat ? Math.round(food.fat) : '?'}g</span>
                </div>
            `;

            div.appendChild(checkbox);
            div.appendChild(content);
            resultsDiv.appendChild(div);
        });

        itemDiv.appendChild(resultsDiv);
        resultsList.appendChild(itemDiv);
    });

    searchResults.style.display = "block";
}

function selectAllResults() {
    resultsList.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = true;
        cb.dispatchEvent(new Event('change'));
    });
}

function deselectAllResults() {
    resultsList.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
}

async function addAllSelected() {
    const toAdd = currentFoodItems.filter(item => item.selected);
    if (toAdd.length === 0) {
        alert("Please select at least one food");
        return;
    }

    try {
        addAllBtn.disabled = true;
        addAllBtn.textContent = "Adding...";

        for (let i = 0; i < toAdd.length; i++) {
            const item = toAdd[i];
            const food = item.selected;
            await logFood(food, item.parsed.quantity);

            if (i < toAdd.length - 1) {
                const delay = Math.random() * 20 + 5;
                await new Promise(resolve => setTimeout(resolve, delay * 1000));
            }
        }

        foodInput.value = "";
        searchResults.style.display = "none";
        currentFoodItems = [];
        loadFoodEntries();
        alert("✅ Foods added successfully!");
    } catch (err) {
        console.error("Error:", err);
        alert(`Error adding foods: ${err.message}`);
    } finally {
        addAllBtn.disabled = false;
        addAllBtn.textContent = "Add All";
    }
}

async function logFood(food, quantity) {
    const payload = {
        date: entryDate.value,
        meal: currentMeal,
        food_id: food.food_id,
        weight_id: food.weight_id,
        quantity: quantity,
        name: food.name,
        calories: food.calories
    };

    if (sessionId) {
        payload.Authorization = `Bearer ${sessionId}`;
        const response = await fetch("/api/food-entries/add", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${sessionId}`
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Failed to log food");
    }

    console.log("✅ Food logged:", food.name);
}

function setupLoginListeners() {
    const loginForm = document.getElementById("login-form");
    const cookieForm = document.getElementById("cookie-form");

    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("username").value.trim();
        const password = document.getElementById("password").value;

        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });

            if (response.ok) {
                const data = await response.json();
                sessionId = data.session_id;
                localStorage.setItem("sessionId", sessionId);
                console.log("✅ Login successful!");
                checkLoginStatus();
                switchTab("food-entries");
            } else {
                const error = await response.json();
                showLoginStatus(error.detail, "error");
            }
        } catch (err) {
            showLoginStatus(`Error: ${err.message}`, "error");
        }
    });

    cookieForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("cookie-username").value.trim();
        const cookie = document.getElementById("cookie-input").value.trim();

        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, cookie })
            });

            if (response.ok) {
                const data = await response.json();
                sessionId = data.session_id;
                localStorage.setItem("sessionId", sessionId);
                console.log("✅ Cookie login successful!");
                checkLoginStatus();
                switchTab("food-entries");
            } else {
                const error = await response.json();
                showLoginStatus(error.detail, "error");
            }
        } catch (err) {
            showLoginStatus(`Error: ${err.message}`, "error");
        }
    });
}

function showLoginStatus(message, type) {
    const status = document.getElementById("login-status");
    status.textContent = message;
    status.className = `login-status ${type}`;
}

async function handleLogout() {
    if (sessionId) {
        await fetch("/api/logout", {
            method: "POST",
            headers: { "Authorization": `Bearer ${sessionId}` }
        }).catch(() => {});
    }
    sessionId = null;
    localStorage.removeItem("sessionId");
    checkLoginStatus();
    switchTab("food-entries");
}

function parseInput(text) {
    const match = text.trim().match(/^(.*?)\s+(\d+(?:\.\d+)?)\s*(\w*)$/);
    if (match) {
        return {
            name: match[1].trim(),
            quantity: parseFloat(match[2]),
            unit: match[3] || "g"
        };
    }
    return { name: text, quantity: 100, unit: "g" };
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// POLAR FLOW FUNCTIONS
// ============================================================================

async function checkPolarFlowStatus() {
    try {
        console.log("🔌 Checking Polar Flow status...");
        const response = await fetch("/api/polar-flow/status");
        const data = await response.json();

        const statusBox = document.getElementById("polar-flow-status");
        const controls = document.getElementById("polar-flow-controls");

        if (data.connected) {
            statusBox.className = "status-box connected";
            statusBox.innerHTML = `✅ Connected to Polar Flow as ${data.username}`;
            controls.style.display = "block";
            console.log("✅ Polar Flow connected");
        } else if (data.configured) {
            statusBox.className = "status-box error";
            statusBox.innerHTML = `❌ ${data.message}`;
            controls.style.display = "none";
            console.warn("⚠️ Polar Flow configured but not connected:", data.message);
        } else {
            statusBox.className = "status-box";
            statusBox.innerHTML = `⚠️ ${data.message}`;
            controls.style.display = "none";
            console.log("ℹ️ Polar Flow not configured:", data.message);
        }
    } catch (err) {
        console.error("❌ Error checking Polar Flow status:", err);
        const statusBox = document.getElementById("polar-flow-status");
        statusBox.className = "status-box error";
        statusBox.innerHTML = "❌ Error checking Polar Flow connection";
    }
}

function setPolarQuick1Week() {
    const endDate = new Date(document.getElementById("polar-end-date").valueAsDate || new Date());
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 7);

    document.getElementById("polar-start-date").valueAsDate = startDate;
    document.getElementById("polar-quick-1-week").classList.add("active");
    document.getElementById("polar-quick-1-month").classList.remove("active");
}

function setPolarQuick1Month() {
    const endDate = new Date(document.getElementById("polar-end-date").valueAsDate || new Date());
    const startDate = new Date(endDate);
    startDate.setMonth(startDate.getMonth() - 1);

    document.getElementById("polar-start-date").valueAsDate = startDate;
    document.getElementById("polar-quick-1-week").classList.remove("active");
    document.getElementById("polar-quick-1-month").classList.add("active");
}

async function fetchPolarActivities() {
    const startDate = document.getElementById("polar-start-date").value;
    const endDate = document.getElementById("polar-end-date").value;

    if (!startDate || !endDate) {
        alert("Please select both start and end dates");
        return;
    }

    try {
        const fetchBtn = document.getElementById("polar-fetch-btn");
        fetchBtn.disabled = true;
        fetchBtn.textContent = "Fetching...";

        console.log(`📥 Fetching Polar Flow activities from ${startDate} to ${endDate}`);

        const response = await fetch(
            `/api/polar-flow/activities?start_date=${startDate}&end_date=${endDate}`
        );

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Failed to fetch activities");
        }

        const data = await response.json();
        polarFlowActivities = data.activities || [];
        console.log(`✅ Fetched ${polarFlowActivities.length} activities`);

        displayPolarActivities();

    } catch (err) {
        console.error("❌ Error fetching activities:", err);
        alert(`Error: ${err.message}`);
    } finally {
        const fetchBtn = document.getElementById("polar-fetch-btn");
        fetchBtn.disabled = false;
        fetchBtn.textContent = "Fetch Activities";
    }
}

function displayPolarActivities() {
    const listDiv = document.getElementById("polar-activities-list");
    const container = document.getElementById("activities-container");

    if (polarFlowActivities.length === 0) {
        listDiv.style.display = "none";
        alert("No activities found for the selected date range");
        return;
    }

    container.innerHTML = "";
    selectedPolarActivities = [];

    polarFlowActivities.forEach((activity, idx) => {
        const item = document.createElement("div");
        item.className = "activity-item";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.dataset.idx = idx;
        checkbox.addEventListener("change", (e) => {
            if (e.target.checked) {
                if (!selectedPolarActivities.includes(idx)) {
                    selectedPolarActivities.push(idx);
                }
            } else {
                selectedPolarActivities = selectedPolarActivities.filter(i => i !== idx);
            }
        });

        // Pre-select first activity
        selectedPolarActivities.push(idx);

        const content = document.createElement("div");
        content.className = "activity-content";
        content.innerHTML = `
            <div class="activity-name">${escapeHtml(activity.name)}</div>
            <div class="activity-details">
                <span>📅 ${activity.date}</span>
                <span>⏱️ ${activity.duration_minutes} minutes</span>
                <span>🔥 ${Math.round(activity.calories)} kcal</span>
            </div>
        `;

        item.appendChild(checkbox);
        item.appendChild(content);
        container.appendChild(item);
    });

    listDiv.style.display = "block";
}

async function syncPolarTMFP() {
    if (!sessionId) {
        alert("Must be logged into MyFitnessPal to sync activities");
        return;
    }

    if (selectedPolarActivities.length === 0) {
        alert("Please select at least one activity to sync");
        return;
    }

    try {
        const syncBtn = document.getElementById("polar-sync-btn");
        const statusDiv = document.getElementById("polar-sync-status");

        syncBtn.disabled = true;
        syncBtn.textContent = "Syncing...";
        statusDiv.className = "status-message info";
        statusDiv.textContent = "Syncing activities to MFP...";

        // Collect selected activities
        const activitiesToSync = selectedPolarActivities.map(idx => polarFlowActivities[idx]);

        console.log(`📤 Syncing ${activitiesToSync.length} activities to MFP`);

        const response = await fetch("/api/polar-flow/sync-to-mfp", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${sessionId}`
            },
            body: JSON.stringify({ activities: activitiesToSync })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Sync failed");
        }

        const data = await response.json();

        statusDiv.className = "status-message success";
        if (data.error_count === 0) {
            statusDiv.textContent = `✅ Successfully synced ${data.synced_count} activities to MFP!`;
        } else {
            statusDiv.textContent = `⚠️ Synced ${data.synced_count} activities, ${data.error_count} errors`;
        }

        console.log("✅ Sync completed:", data);

    } catch (err) {
        console.error("❌ Sync error:", err);
        const statusDiv = document.getElementById("polar-sync-status");
        statusDiv.className = "status-message error";
        statusDiv.textContent = `❌ Error: ${err.message}`;
    } finally {
        const syncBtn = document.getElementById("polar-sync-btn");
        syncBtn.disabled = false;
        syncBtn.textContent = "Sync Selected to MFP";
    }
}
