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
const caloriesSummary = document.getElementById("calorie-summary");

// Date navigation buttons
const datePrevWeekBtn = document.getElementById("date-prev-week-btn");
const datePrevDayBtn = document.getElementById("date-prev-day-btn");
const dateNextDayBtn = document.getElementById("date-next-day-btn");
const dateNextWeekBtn = document.getElementById("date-next-week-btn");

let currentFoodItems = [];
let polarFlowActivities = [];
let selectedPolarActivities = [];
let currentFoodView = "table";  // "table" or "cards"
let filteredFoodDatabase = [];

// Modal elements
const loadMoreFoodsBtn = document.getElementById("load-more-foods-btn");
const loadFoodsModal = document.getElementById("load-foods-modal");
const closeModalBtn = document.getElementById("close-modal-btn");
const startDateInput = document.getElementById("foods-start-date");
const endDateInput = document.getElementById("foods-end-date");
const quick1WeekBtn = document.getElementById("quick-1-week");
const quick1MonthBtn = document.getElementById("quick-1-month");
const loadFoodsConfirmBtn = document.getElementById("load-foods-confirm");
const loadFoodsStatus = document.getElementById("load-foods-status");

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

    // Handle URL hash changes
    window.addEventListener("hashchange", () => {
        const hash = window.location.hash.slice(1) || "food-entries";
        switchTab(hash);
    });

    // Load initial tab from URL or default
    const initialTab = window.location.hash.slice(1) || "food-instances";
    switchTab(initialTab);

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

    // Auto-load when date changes
    entryDate.addEventListener("change", loadFoodEntries);

    // Date navigation buttons
    if (datePrevWeekBtn) datePrevWeekBtn.addEventListener("click", () => changeDate(-7));
    if (datePrevDayBtn) datePrevDayBtn.addEventListener("click", () => changeDate(-1));
    if (dateNextDayBtn) dateNextDayBtn.addEventListener("click", () => changeDate(1));
    if (dateNextWeekBtn) dateNextWeekBtn.addEventListener("click", () => changeDate(7));

    // Pre-fill meal select based on current time
    initializeMealSelect();

    // Login sub-tabs
    document.querySelectorAll("[data-subtab]").forEach(btn => {
        btn.addEventListener("click", () => switchLoginTab(btn.dataset.subtab));
    });

    // Polar Flow event listeners
    const polarStartDate = document.getElementById("polar-start-date");
    const polarEndDate = document.getElementById("polar-end-date");
    const polarQuickToday = document.getElementById("polar-quick-today");
    const polarQuick1Week = document.getElementById("polar-quick-1-week");
    const polarQuick1Month = document.getElementById("polar-quick-1-month");
    const polarFetchBtn = document.getElementById("polar-fetch-btn");
    const polarSyncBtn = document.getElementById("polar-sync-btn");

    if (polarStartDate) polarStartDate.valueAsDate = new Date();
    if (polarEndDate) polarEndDate.valueAsDate = new Date();

    if (polarQuickToday) polarQuickToday.addEventListener("click", setPolarQuickToday);
    if (polarQuick1Week) polarQuick1Week.addEventListener("click", setPolarQuick1Week);
    if (polarQuick1Month) polarQuick1Month.addEventListener("click", setPolarQuick1Month);
    if (polarFetchBtn) polarFetchBtn.addEventListener("click", fetchPolarActivities);
    if (polarSyncBtn) polarSyncBtn.addEventListener("click", syncPolarTMFP);

    // Food Library controls
    const foodSearchInput = document.getElementById("food-search-input");
    const foodSearchTypeRadios = document.querySelectorAll("input[name='search-type']");
    const foodSortSelect = document.getElementById("food-sort-select");
    const foodViewBtns = document.querySelectorAll(".view-btn");

    if (foodSearchInput) {
        foodSearchInput.addEventListener("input", () => {
            applyFoodFiltersAndSort();
        });
    }

    foodSearchTypeRadios.forEach(radio => {
        radio.addEventListener("change", () => {
            applyFoodFiltersAndSort();
        });
    });

    if (foodSortSelect) {
        foodSortSelect.addEventListener("change", () => {
            applyFoodFiltersAndSort();
        });
    }

    foodViewBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            switchFoodView(btn.dataset.view);
        });
    });

    // Modal listeners
    if (loadMoreFoodsBtn) loadMoreFoodsBtn.addEventListener("click", openLoadFoodsModal);
    if (closeModalBtn) closeModalBtn.addEventListener("click", closeLoadFoodsModal);
    if (loadFoodsModal) {
        loadFoodsModal.addEventListener("click", (e) => {
            if (e.target === loadFoodsModal) closeLoadFoodsModal();
        });
    }
    if (quick1WeekBtn) quick1WeekBtn.addEventListener("click", setQuick1Week);
    if (quick1MonthBtn) quick1MonthBtn.addEventListener("click", setQuick1Month);
    if (loadFoodsConfirmBtn) loadFoodsConfirmBtn.addEventListener("click", loadFoodsFromRange);

    // Set default dates for modal
    if (endDateInput) endDateInput.valueAsDate = new Date();

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
    // Update URL hash
    window.history.replaceState(null, "", `#${tabName}`);

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
    // Update count
    foodInstancesCount.textContent = `Total: ${foods.length} foods`;

    if (foods.length === 0) {
        if (currentFoodView === "table") {
            document.getElementById("food-table-body").innerHTML = '<tr><td colspan="8" class="no-results">No foods in database</td></tr>';
        } else {
            foodInstancesList.innerHTML = '<div class="empty-state">No foods in database. Add foods in the "Today\'s Entries" tab.</div>';
        }
        return;
    }

    if (currentFoodView === "table") {
        displayFoodTable(foods);
    } else {
        displayFoodCards(foods);
    }
}

function displayFoodTable(foods) {
    const tbody = document.getElementById("food-table-body");
    tbody.innerHTML = "";

    if (foods.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="no-results">No foods match your search</td></tr>';
        return;
    }

    foods.forEach(food => {
        const tr = document.createElement("tr");
        const measurement = food.measurement ? `${food.measurement.value}${food.measurement.unit}` : "N/A";
        tr.innerHTML = `
            <td>${escapeHtml(food.name)}</td>
            <td class="measurement">${measurement}</td>
            <td class="numeric">${Math.round(food.calories)}</td>
            <td class="numeric">${food.protein ? Math.round(food.protein) : '-'}</td>
            <td class="numeric">${food.carbs ? Math.round(food.carbs) : '-'}</td>
            <td class="numeric">${food.fat ? Math.round(food.fat) : '-'}</td>
            <td class="numeric">${food.fiber ? Math.round(food.fiber) : '-'}</td>
            <td class="numeric">${food.sugar ? Math.round(food.sugar) : '-'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function displayFoodCards(foods) {
    foodInstancesList.innerHTML = "";

    if (foods.length === 0) {
        foodInstancesList.innerHTML = '<div class="empty-state">No foods match your search</div>';
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

        // Try to load from diary cache first
        const response = await fetch(`/api/diary-entries?date_str=${dateStr}`);
        const data = await response.json();
        foodEntries = data.meals || {};

        // If no diary data, try online API
        if (!data.has_data && sessionId) {
            const onlineResponse = await fetch(`/api/food-entries?date_str=${dateStr}`, {
                headers: { "Authorization": `Bearer ${sessionId}` }
            });
            const onlineData = await onlineResponse.json();
            foodEntries = onlineData.meals || {};
        }

        displayFoodEntries(foodEntries);
        updateCalorieSummary(data);
    } catch (err) {
        console.warn("Note: Food entries not available, using local data");
        displayFoodEntries({});
    }
}

function updateCalorieSummary(diaryData) {
    const caloriesSummary = document.getElementById("calorie-summary");
    if (!caloriesSummary) return;

    const totals = diaryData.totals || {};
    const consumed = totals.calories || 0;
    const goalCalories = 2000; // Default goal
    const exerciseCalories = 0; // No exercise data in diary
    const remaining = goalCalories - consumed + exerciseCalories;

    // Update progress bar
    const percentage = Math.min((consumed / goalCalories) * 100, 100);
    const eatenBar = document.getElementById("eaten-bar");
    if (eatenBar) eatenBar.style.width = percentage + "%";

    // Update goal marker position
    const goalMarker = document.getElementById("goal-marker");
    if (goalMarker) goalMarker.style.left = "100%";

    // Update text values
    const eatenVal = document.getElementById("eaten-val");
    if (eatenVal) eatenVal.textContent = consumed;
    const eatenValStat = document.getElementById("eaten-val-stat");
    if (eatenValStat) eatenValStat.textContent = consumed + " cal";

    const goalLabel = document.getElementById("goal-label");
    if (goalLabel) goalLabel.textContent = goalCalories;

    const exerciseVal = document.getElementById("exercise-val");
    if (exerciseVal) exerciseVal.textContent = exerciseCalories + " cal";

    const remainingVal = document.getElementById("remaining-val");
    if (remainingVal) remainingVal.textContent = Math.max(remaining, 0);

    const remainingValStat = document.getElementById("remaining-val-stat");
    if (remainingValStat) remainingValStat.textContent = Math.max(remaining, 0) + " cal";

    caloriesSummary.style.display = "block";
}

function changeDate(dayOffset) {
    const currentDate = new Date(entryDate.valueAsDate);
    currentDate.setDate(currentDate.getDate() + dayOffset);
    entryDate.valueAsDate = currentDate;
    loadFoodEntries();
}

async function initializeMealSelect() {
    try {
        const response = await fetch("/api/meal-schedule");
        const data = await response.json();
        currentMeal = data.current_meal;
        mealSelect.value = currentMeal;
        console.log(`🍽️ Set meal to: ${currentMeal}`);
    } catch (err) {
        console.warn("Could not determine meal from schedule, defaulting to snacks");
        mealSelect.value = "snacks";
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
        showNotification("Please select at least one food", "warning");
        return;
    }

    try {
        addAllBtn.disabled = true;
        addAllBtn.textContent = "Adding...";

        let successCount = 0;
        for (let i = 0; i < toAdd.length; i++) {
            const item = toAdd[i];
            const food = item.selected;
            const result = await logFood(food, item.parsed.quantity);
            if (result) successCount++;

            if (i < toAdd.length - 1) {
                const delay = Math.random() * 20 + 5;
                await new Promise(resolve => setTimeout(resolve, delay * 1000));
            }
        }

        // Only show success message if foods were actually added
        if (successCount > 0) {
            foodInput.value = "";
            searchResults.style.display = "none";
            currentFoodItems = [];
            await loadFoodEntries();
            showNotification(`✅ ${successCount} food${successCount > 1 ? 's' : ''} added successfully!`, "success");
        } else {
            showNotification("⚠️ Foods could not be added. Please try again.", "error");
        }
    } catch (err) {
        console.error("Error:", err);
        showNotification(`Error adding foods: ${err.message}`, "error");
    } finally {
        addAllBtn.disabled = false;
        addAllBtn.textContent = "Add All";
    }
}

function showNotification(message, type) {
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 16px;
        background: ${type === 'success' ? '#d4edda' : type === 'warning' ? '#fff3cd' : '#f8d7da'};
        color: ${type === 'success' ? '#155724' : type === 'warning' ? '#856404' : '#721c24'};
        border: 1px solid ${type === 'success' ? '#c3e6cb' : type === 'warning' ? '#ffeaa7' : '#f5c6cb'};
        border-radius: 4px;
        font-size: 14px;
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
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
        const response = await fetch("/api/food-entries/add", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${sessionId}`
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            console.error("Server rejected food entry:", food.name);
            return false;
        }
        console.log("✅ Food logged to server:", food.name);
        return true;
    }

    // Local-only mode (no server)
    console.log("✅ Food recorded locally:", food.name);
    return true;
}

function setupLoginListeners() {
    const loginForm = document.getElementById("login-form");
    const cookieForm = document.getElementById("cookie-form");

    // Skip if login forms don't exist (login tab removed)
    if (!loginForm || !cookieForm) return;

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
    if (!status) return; // Element doesn't exist (login tab removed)
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

function setPolarQuickToday() {
    const today = new Date();
    document.getElementById("polar-start-date").valueAsDate = today;
    document.getElementById("polar-end-date").valueAsDate = today;

    document.getElementById("polar-quick-today").classList.add("active");
    document.getElementById("polar-quick-1-week").classList.remove("active");
    document.getElementById("polar-quick-1-month").classList.remove("active");
}

function setPolarQuick1Week() {
    const endDate = new Date(document.getElementById("polar-end-date").valueAsDate || new Date());
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 7);

    document.getElementById("polar-start-date").valueAsDate = startDate;
    document.getElementById("polar-quick-today").classList.remove("active");
    document.getElementById("polar-quick-1-week").classList.add("active");
    document.getElementById("polar-quick-1-month").classList.remove("active");
}

function setPolarQuick1Month() {
    const endDate = new Date(document.getElementById("polar-end-date").valueAsDate || new Date());
    const startDate = new Date(endDate);
    startDate.setMonth(startDate.getMonth() - 1);

    document.getElementById("polar-start-date").valueAsDate = startDate;
    document.getElementById("polar-quick-today").classList.remove("active");
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

// ============================================================================
// FOOD LIBRARY FILTERING AND SORTING
// ============================================================================

function applyFoodFiltersAndSort() {
    const searchInput = document.getElementById("food-search-input").value.trim();
    const searchType = document.querySelector("input[name='search-type']:checked").value;
    const sortType = document.getElementById("food-sort-select").value;

    let filtered = [...localFoodDatabase];

    // Apply search filter
    if (searchInput) {
        filtered = filterFoods(filtered, searchInput, searchType);
    }

    // Apply sorting
    filtered = sortFoods(filtered, sortType);

    // Update display
    filteredFoodDatabase = filtered;
    displayFoodInstances(filtered);
}

function filterFoods(foods, query, searchType) {
    if (searchType === "regex") {
        // Regex search
        try {
            const regex = new RegExp(query, "i");
            return foods.filter(food =>
                regex.test(food.name) ||
                regex.test(food.brand || "") ||
                regex.test(food.type || "")
            );
        } catch (err) {
            console.error("❌ Invalid regex:", err);
            alert(`Invalid regex pattern: ${err.message}`);
            return foods;
        }
    } else {
        // Normal text search
        const lowerQuery = query.toLowerCase();
        return foods.filter(food =>
            food.name.toLowerCase().includes(lowerQuery) ||
            (food.brand && food.brand.toLowerCase().includes(lowerQuery)) ||
            (food.type && food.type.toLowerCase().includes(lowerQuery))
        );
    }
}

function sortFoods(foods, sortType) {
    const sorted = [...foods];

    switch (sortType) {
        case "name":
            sorted.sort((a, b) => a.name.localeCompare(b.name));
            break;
        case "name-desc":
            sorted.sort((a, b) => b.name.localeCompare(a.name));
            break;
        case "calories":
            sorted.sort((a, b) => (a.calories || 0) - (b.calories || 0));
            break;
        case "calories-desc":
            sorted.sort((a, b) => (b.calories || 0) - (a.calories || 0));
            break;
        case "protein":
            sorted.sort((a, b) => (a.protein || 0) - (b.protein || 0));
            break;
        case "protein-desc":
            sorted.sort((a, b) => (b.protein || 0) - (a.protein || 0));
            break;
        case "carbs":
            sorted.sort((a, b) => (a.carbs || 0) - (b.carbs || 0));
            break;
        case "carbs-desc":
            sorted.sort((a, b) => (b.carbs || 0) - (a.carbs || 0));
            break;
        case "fat":
            sorted.sort((a, b) => (a.fat || 0) - (b.fat || 0));
            break;
        case "fat-desc":
            sorted.sort((a, b) => (b.fat || 0) - (a.fat || 0));
            break;
    }

    return sorted;
}

function switchFoodView(view) {
    currentFoodView = view;

    // Update button states
    document.querySelectorAll(".view-btn").forEach(btn => {
        if (btn.dataset.view === view) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    // Show/hide views
    const tableContainer = document.getElementById("food-table-container");
    const cardsList = document.getElementById("food-instances-list");

    if (view === "table") {
        tableContainer.style.display = "block";
        cardsList.style.display = "none";
    } else {
        tableContainer.style.display = "none";
        cardsList.style.display = "block";
    }

    // Re-render with current filtered data
    displayFoodInstances(filteredFoodDatabase);
}

// Modal functions
function openLoadFoodsModal() {
    if (!sessionId) {
        alert("Please login to MFP first to load more foods");
        return;
    }
    if (loadFoodsModal) {
        loadFoodsModal.style.display = "flex";
    }
}

function closeLoadFoodsModal() {
    if (loadFoodsModal) {
        loadFoodsModal.style.display = "none";
    }
    if (loadFoodsStatus) {
        loadFoodsStatus.textContent = "";
    }
}

function setQuick1Week() {
    const endDate = new Date(endDateInput.value || new Date());
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 7);

    if (startDateInput) startDateInput.valueAsDate = startDate;
    if (endDateInput) endDateInput.valueAsDate = endDate;
}

function setQuick1Month() {
    const endDate = new Date(endDateInput.value || new Date());
    const startDate = new Date(endDate);
    startDate.setMonth(startDate.getMonth() - 1);

    if (startDateInput) startDateInput.valueAsDate = startDate;
    if (endDateInput) endDateInput.valueAsDate = endDate;
}

async function loadFoodsFromRange() {
    if (!sessionId || !startDateInput || !endDateInput) return;

    try {
        if (loadFoodsConfirmBtn) loadFoodsConfirmBtn.disabled = true;
        if (loadFoodsStatus) loadFoodsStatus.textContent = "Loading foods...";

        const startDate = startDateInput.value;
        const endDate = endDateInput.value;

        console.log(`\n📥 LOADING FOODS FROM RANGE: ${startDate} to ${endDate}`);

        const response = await fetch(`/api/foods/range?start_date=${startDate}&end_date=${endDate}`, {
            headers: { "Authorization": `Bearer ${sessionId}` },
        });

        if (!response.ok) {
            throw new Error(`Failed to load foods: ${response.status}`);
        }

        const data = await response.json();
        const newFoods = data.foods || [];

        console.log(`✅ Loaded ${newFoods.length} foods from range`);

        // Merge with existing database (avoid duplicates)
        const existingNames = new Set(localFoodDatabase.map(f => f.name));
        const uniqueNewFoods = newFoods.filter(f => !existingNames.has(f.name));

        localFoodDatabase = [...localFoodDatabase, ...uniqueNewFoods];

        console.log(`📚 Database now has ${localFoodDatabase.length} total foods`);

        if (loadFoodsStatus) {
            loadFoodsStatus.textContent = `✅ Added ${uniqueNewFoods.length} new foods. Database now has ${localFoodDatabase.length} foods.`;
        }

        // Refresh the food display
        applyFoodFiltersAndSort();

        setTimeout(() => {
            closeLoadFoodsModal();
        }, 2000);
    } catch (err) {
        console.error("❌ Error loading foods:", err);
        if (loadFoodsStatus) {
            loadFoodsStatus.textContent = `❌ Error: ${err.message}`;
        }
    } finally {
        if (loadFoodsConfirmBtn) loadFoodsConfirmBtn.disabled = false;
    }
}
