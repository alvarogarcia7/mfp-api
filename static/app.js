// Global state
let sessionId = null;
let currentMeal = "breakfast";

// DOM elements
const loginScreen = document.getElementById("login-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const loginForm = document.getElementById("login-form");
const cookieForm = document.getElementById("cookie-form");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const cookieUsernameInput = document.getElementById("cookie-username");
const cookieInput = document.getElementById("cookie-input");
const loginError = document.getElementById("login-error");
const cookieError = document.getElementById("cookie-error");
const logoutBtn = document.getElementById("logout-btn");
const tabBtns = document.querySelectorAll(".tab-btn");
const loginTabs = document.querySelectorAll(".login-tab");
const mealSelect = document.getElementById("meal-select");
const foodInput = document.getElementById("food-input");
const searchBtn = document.getElementById("search-btn");
const searchResults = document.getElementById("search-results");
const resultsList = document.getElementById("results-list");
const selectAllBtn = document.getElementById("select-all-btn");
const deselectAllBtn = document.getElementById("deselect-all-btn");
const addAllBtn = document.getElementById("add-all-btn");
const refreshBtn = document.getElementById("refresh-btn");

// Store current food items being processed
let currentFoodItems = [];

// Store debug info from server responses
let entryDebugInfo = {};

// Local food database
let localFoodDatabase = [];
let dbInitialized = false;

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
    sessionId = localStorage.getItem("sessionId");
    if (sessionId) {
        // Verify sessionId is still valid
        verifySessionAndInit();
    } else {
        showLogin();
        loadSavedCredentials();
    }

    // Event listeners
    loginForm.addEventListener("submit", handleLogin);
    cookieForm.addEventListener("submit", handleCookieLogin);
    logoutBtn.addEventListener("click", handleLogout);
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
    refreshBtn.addEventListener("click", loadToday);

    // Modal listeners
    loadMoreFoodsBtn.addEventListener("click", openLoadFoodsModal);
    closeModalBtn.addEventListener("click", closeLoadFoodsModal);
    loadFoodsModal.addEventListener("click", (e) => {
        if (e.target === loadFoodsModal) closeLoadFoodsModal();
    });
    quick1WeekBtn.addEventListener("click", setQuick1Week);
    quick1MonthBtn.addEventListener("click", setQuick1Month);
    loadFoodsConfirmBtn.addEventListener("click", loadFoodsFromRange);

    // Tab switching
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
});

function switchTab(tabName) {
    // Update button states
    tabBtns.forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    // Show/hide forms
    loginTabs.forEach(tab => {
        if (tab.dataset.tab === tabName) {
            tab.classList.add("active");
        } else {
            tab.classList.remove("active");
        }
    });

    // Clear errors
    loginError.textContent = "";
    cookieError.textContent = "";
}

function showLogin() {
    loginScreen.classList.add("active");
    dashboardScreen.classList.remove("active");
}

function showDashboard() {
    loginScreen.classList.remove("active");
    dashboardScreen.classList.add("active");
}

function loadSavedCredentials() {
    const savedUsername = localStorage.getItem("savedUsername");
    const savedPassword = localStorage.getItem("savedPassword");
    const savedCookieUsername = localStorage.getItem("savedCookieUsername");
    const savedCookie = localStorage.getItem("savedCookie");

    if (savedUsername && savedPassword) {
        usernameInput.value = savedUsername;
        passwordInput.value = savedPassword;
    }

    if (savedCookieUsername && savedCookie) {
        cookieUsernameInput.value = savedCookieUsername;
        cookieInput.value = savedCookie;
    }
}

async function verifySessionAndInit() {
    try {
        console.log("🔐 Verifying sessionId...");
        const response = await fetch("/api/today", {
            headers: { "Authorization": `Bearer ${sessionId}` },
        });

        if (response.ok) {
            console.log("✅ SessionId is valid");
            showDashboard();
            loadToday();
            return;
        }

        if (response.status === 401) {
            console.warn("⚠️ SessionId expired (401), attempting auto-login...");
            sessionId = null;
            localStorage.removeItem("sessionId");

            // Try auto-login with saved credentials
            await attemptAutoLogin();
            return;
        }

        // Other errors - show login
        throw new Error(`Unexpected response: ${response.status}`);
    } catch (err) {
        console.error("❌ Session verification failed:", err);
        showLogin();
        loadSavedCredentials();
    }
}

async function attemptAutoLogin() {
    const savedUsername = localStorage.getItem("savedUsername");
    const savedPassword = localStorage.getItem("savedPassword");
    const savedCookieUsername = localStorage.getItem("savedCookieUsername");
    const savedCookie = localStorage.getItem("savedCookie");

    // Try password login first
    if (savedUsername && savedPassword) {
        console.log("🔄 Auto-login with password...");
        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: savedUsername, password: savedPassword }),
            });

            if (response.ok) {
                const data = await response.json();
                sessionId = data.session_id;
                localStorage.setItem("sessionId", sessionId);
                console.log("✅ Auto-login successful");
                await initializeFoodDatabase();
                showDashboard();
                loadToday();
                return;
            }
        } catch (err) {
            console.warn("⚠️ Password auto-login failed:", err);
        }
    }

    // Try cookie login second
    if (savedCookieUsername && savedCookie) {
        console.log("🔄 Auto-login with cookie...");
        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: savedCookieUsername, cookie: savedCookie }),
            });

            if (response.ok) {
                const data = await response.json();
                sessionId = data.session_id;
                localStorage.setItem("sessionId", sessionId);
                console.log("✅ Auto-login successful");
                await initializeFoodDatabase();
                showDashboard();
                loadToday();
                return;
            }
        } catch (err) {
            console.warn("⚠️ Cookie auto-login failed:", err);
        }
    }

    // Auto-login failed, show login screen
    console.log("❌ Auto-login failed, showing login screen");
    showLogin();
    loadSavedCredentials();
}

async function handleLogin(e) {
    e.preventDefault();
    loginError.textContent = "";

    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    if (!username || !password) {
        loginError.textContent = "Please enter username and password";
        return;
    }

    await performLogin({ username, password }, loginError);

    if (sessionId) {
        localStorage.setItem("savedUsername", username);
        localStorage.setItem("savedPassword", password);
        usernameInput.value = "";
        passwordInput.value = "";
    }
}

async function handleCookieLogin(e) {
    e.preventDefault();
    cookieError.textContent = "";

    const username = cookieUsernameInput.value.trim();
    const cookie = cookieInput.value.trim();

    if (!username) {
        cookieError.textContent = "Please enter your MyFitnessPal username";
        return;
    }

    if (!cookie) {
        cookieError.textContent = "Please paste your session cookie";
        return;
    }

    await performLogin({ username, cookie }, cookieError);

    if (sessionId) {
        localStorage.setItem("savedCookieUsername", username);
        localStorage.setItem("savedCookie", cookie);
        cookieUsernameInput.value = "";
        cookieInput.value = "";
    }
}

async function performLogin(credentials, errorElement) {
    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials),
        });

        if (!response.ok) {
            const error = await response.json();
            errorElement.textContent = error.detail || "Login failed";
            console.error("Login error:", error);
            return;
        }

        const data = await response.json();
        sessionId = data.session_id;
        localStorage.setItem("sessionId", sessionId);

        console.log("Login successful, session:", sessionId);
        console.log("📚 Initializing local food database from last 7 days...");
        await initializeFoodDatabase();
        showDashboard();
        loadToday();
    } catch (err) {
        errorElement.textContent = `Error: ${err.message}`;
        console.error("Login error:", err);
    }
}

function handleLogout() {
    if (!sessionId) return;

    fetch("/api/logout", {
        method: "POST",
        headers: { "Authorization": `Bearer ${sessionId}` },
    }).catch(() => {});

    sessionId = null;
    localStorage.removeItem("sessionId");
    showLogin();
}

async function loadToday() {
    if (!sessionId) return;

    try {
        const response = await fetch("/api/today", {
            headers: { "Authorization": `Bearer ${sessionId}` },
        });

        if (!response.ok) throw new Error("Failed to load today");

        const data = await response.json();
        updateDashboard(data);
    } catch (err) {
        console.error(err);
        alert(`Error loading data: ${err.message}`);
    }
}

function updateDashboard(data) {
    // Update header
    const today = new Date();
    const dateStr = today.toLocaleDateString("en-US", {
        weekday: "long",
        month: "short",
        day: "numeric",
    });
    document.getElementById("date-header").textContent = dateStr;

    // Update calorie stats
    const goal = data.goal_calories || 2000;
    const eaten = data.calories_eaten || 0;
    const exercise = data.exercise_calories || 0;
    const remaining = data.remaining || 0;

    document.getElementById("eaten-label").textContent = Math.round(eaten);
    document.getElementById("goal-label").textContent = Math.round(goal);
    document.getElementById("eaten-val").textContent = Math.round(eaten);
    document.getElementById("exercise-val").textContent = Math.round(exercise);
    document.getElementById("remaining-val").textContent = Math.round(remaining);

    // Update calorie bar
    const eatenPercent = Math.min((eaten / goal) * 100, 100);
    const goalPercent = (goal / Math.max(goal, eaten)) * 100;
    document.getElementById("eaten-bar").style.width = eatenPercent + "%";
    document.getElementById("goal-marker").style.left = goalPercent + "%";

    // Update meals
    const mealsData = data.meals || {};
    ["breakfast", "lunch", "dinner", "snacks"].forEach((meal) => {
        const entries = mealsData[meal] || [];
        const entryList = document.getElementById(`${meal}-entries`);
        entryList.innerHTML = "";

        if (entries.length === 0) {
            entryList.innerHTML = '<li class="empty-state">No entries yet</li>';
        } else {
            entries.forEach((entry, idx) => {
                const li = document.createElement("li");
                const calories = Math.round(entry.calories || 0);
                const isExcessive = calories > goal;
                const liClass = isExcessive ? 'class="excessive-entry"' : '';
                li.innerHTML = `
                    <span class="entry-name">${escapeHtml(entry.name)}</span>
                    <span class="entry-calories">${calories} cal</span>
                `;
                if (isExcessive) {
                    li.classList.add("excessive-entry");
                }

                // Add debug info if available
                const debugKeys = Object.keys(entryDebugInfo);
                if (debugKeys.length > 0) {
                    const debugDiv = document.createElement("div");
                    debugDiv.className = "entry-debug";
                    debugDiv.textContent = JSON.stringify(entryDebugInfo[debugKeys[debugKeys.length - 1]], null, 2);
                    li.appendChild(debugDiv);
                    debugKeys.pop();
                }

                entryList.appendChild(li);
            });
        }
    });

    // Clear search results
    searchResults.style.display = "none";
    resultsList.innerHTML = "";
    foodInput.value = "";
}

async function initializeFoodDatabase() {
    if (dbInitialized) {
        console.log("📚 Food database already initialized");
        return;
    }

    try {
        console.log("📡 Fetching food database from server...");
        const response = await fetch("/api/foods/recent", {
            headers: { "Authorization": `Bearer ${sessionId}` },
        });

        if (!response.ok) {
            console.warn("⚠️ Failed to fetch recent foods:", response.status);
            return;
        }

        const data = await response.json();
        localFoodDatabase = data.foods || [];
        dbInitialized = true;

        const cacheStatus = data.cached ? "📦 (cached)" : "🔄 (fetched)";
        console.log(`✅ Initialized database with ${localFoodDatabase.length} foods ${cacheStatus}`);
        console.log("📋 Available foods:", localFoodDatabase);
    } catch (err) {
        console.error("❌ Error initializing food database:", err);
    }
}

function searchLocalFoods(query) {
    if (!query || query.length === 0) {
        return [];
    }

    const queryLower = query.toLowerCase();
    return localFoodDatabase.filter(food =>
        food.name.toLowerCase().includes(queryLower)
    ).slice(0, 5);  // Return top 5 matches
}

function openLoadFoodsModal() {
    loadFoodsModal.style.display = "flex";
    const today = new Date();
    endDateInput.valueAsDate = today;
    loadFoodsStatus.textContent = "";
}

function closeLoadFoodsModal() {
    loadFoodsModal.style.display = "none";
    startDateInput.value = "";
    endDateInput.value = "";
    loadFoodsStatus.textContent = "";
}

function setQuick1Week() {
    const end = new Date(endDateInput.valueAsDate || new Date());
    const start = new Date(end);
    start.setDate(start.getDate() - 7);

    startDateInput.valueAsDate = start;
    quick1WeekBtn.classList.add("active");
    quick1MonthBtn.classList.remove("active");
}

function setQuick1Month() {
    const end = new Date(endDateInput.valueAsDate || new Date());
    const start = new Date(end);
    start.setMonth(start.getMonth() - 1);

    startDateInput.valueAsDate = start;
    quick1WeekBtn.classList.remove("active");
    quick1MonthBtn.classList.add("active");
}

async function loadFoodsFromRange() {
    if (!sessionId || !startDateInput.value || !endDateInput.value) {
        alert("Please select both start and end dates");
        return;
    }

    try {
        loadFoodsConfirmBtn.disabled = true;
        loadFoodsStatus.textContent = "Loading foods...";

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

        loadFoodsStatus.textContent = `✅ Added ${uniqueNewFoods.length} new foods. Database now has ${localFoodDatabase.length} foods.`;

        setTimeout(() => {
            closeLoadFoodsModal();
        }, 2000);
    } catch (err) {
        console.error("❌ Error loading foods:", err);
        loadFoodsStatus.textContent = `❌ Error: ${err.message}`;
    } finally {
        loadFoodsConfirmBtn.disabled = false;
    }
}

async function handleSearch() {
    const text = foodInput.value.trim();
    if (!text || !sessionId) return;

    // Parse multiline input
    const lines = text.split('\n').map(l => l.trim()).filter(l => l);
    if (lines.length === 0) return;

    try {
        console.log("\n🔍 SEARCHING: Local database first, then MFP API");

        if (!dbInitialized || localFoodDatabase.length === 0) {
            console.warn("⚠️ Local database not initialized, using MFP API");
        }

        // Search for all food items
        currentFoodItems = [];

        for (const line of lines) {
            const parsed = parseInput(line);
            console.log(`\n🔍 SEARCHING FOR: ${parsed.name} (${parsed.quantity}${parsed.unit})`);

            // Try local database first
            console.log("📚 Searching local database first...");
            let results = searchLocalFoods(parsed.name);

            if (results.length > 0) {
                console.log(`✅ Found ${results.length} results in local database`);
                console.log("🥇 Top result:", results[0]);
            } else {
                // Fallback to MFP API search
                console.log("⚠️ Not found locally, querying MFP API...");
                try {
                    const response = await fetch("/api/search", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${sessionId}`,
                        },
                        body: JSON.stringify({ query: parsed.name }),
                    });

                    if (response.ok) {
                        const data = await response.json();
                        results = data.results || [];
                        console.log(`✅ Found ${results.length} results from MFP API`);
                        if (results.length > 0) {
                            console.log("🥇 Top result:", results[0]);
                        }
                    } else {
                        console.warn(`⚠️ MFP API search failed: ${response.status}`);
                    }
                } catch (err) {
                    console.warn("⚠️ MFP API search error:", err);
                }
            }

            if (results.length > 0) {
                // Convert results to compatible format
                const formattedResults = results.map(food => ({
                    name: food.name,
                    calories: food.calories,
                    protein: food.protein,
                    carbs: food.carbs,
                    fat: food.fat,
                    food_id: food.food_id,
                    weight_id: food.weight_id,
                }));

                // Store with metadata
                currentFoodItems.push({
                    query: line,
                    parsed: parsed,
                    results: formattedResults,
                    selected: formattedResults[0], // Pre-select first (most likely)
                });
            } else {
                console.warn(`⚠️ No results found for "${parsed.name}"`);
            }
        }

        if (currentFoodItems.length > 0) {
            showResults();
        } else {
            alert("No foods found. Try a different search term.");
        }
    } catch (err) {
        console.error("❌ Search error:", err);
        alert(`Search error: ${err.message}`);
    }
}

function showResults() {
    resultsList.innerHTML = "";

    currentFoodItems.forEach((item, itemIdx) => {
        const itemDiv = document.createElement("div");
        itemDiv.style.marginBottom = "20px";
        itemDiv.style.paddingBottom = "20px";
        itemDiv.style.borderBottom = "1px solid #eee";

        // Query header
        const header = document.createElement("div");
        header.style.fontWeight = "600";
        header.style.marginBottom = "10px";
        header.style.color = "#333";
        header.textContent = `${item.query} → ${item.parsed.quantity}${item.parsed.unit}`;
        itemDiv.appendChild(header);

        // Results for this query
        const resultsDiv = document.createElement("div");
        resultsDiv.style.display = "flex";
        resultsDiv.style.flexDirection = "column";
        resultsDiv.style.gap = "8px";

        item.results.forEach((food, foodIdx) => {
            const div = document.createElement("div");
            div.className = "result-item";

            // Pre-select the first (most likely) result
            if (foodIdx === 0) {
                div.classList.add("pre-selected");
            }

            const calories = Math.round(food.calories || 0);
            const protein = food.protein ? Math.round(food.protein) : "?";
            const carbs = food.carbs ? Math.round(food.carbs) : "?";
            const fat = food.fat ? Math.round(food.fat) : "?";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = (foodIdx === 0); // Pre-select first
            checkbox.dataset.itemIdx = itemIdx;
            checkbox.dataset.foodIdx = foodIdx;
            checkbox.addEventListener("change", (e) => {
                if (e.target.checked) {
                    item.selected = food;
                    // Uncheck other options for this item
                    resultsList.querySelectorAll(`input[data-itemIdx="${itemIdx}"]`).forEach(cb => {
                        if (cb !== checkbox) cb.checked = false;
                    });
                }
            });

            const content = document.createElement("div");
            content.className = "result-content";
            content.innerHTML = `
                <div class="result-name">${escapeHtml(food.name)}</div>
                <div class="result-meta">
                    <span>${calories} cal</span>
                    <span>P: ${protein}g</span>
                    <span>C: ${carbs}g</span>
                    <span>F: ${fat}g</span>
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
    if (!sessionId) return;

    const toAdd = currentFoodItems.filter(item => item.selected);
    if (toAdd.length === 0) {
        alert("Please select at least one food");
        return;
    }

    try {
        addAllBtn.disabled = true;
        addAllBtn.textContent = "Adding...";

        console.log(`\n📋 BATCH OPERATION: Adding ${toAdd.length} items`);

        let csrf = null;
        if (toAdd.length > 0) {
            console.log("🔐 Fetching CSRF token...");
            const csrfResp = await fetch("/api/csrf", {
                headers: { "Authorization": `Bearer ${sessionId}` },
            });
            console.log("📥 CSRF response status:", csrfResp.status, csrfResp.statusText);
            if (csrfResp.ok) {
                const csrfData = await csrfResp.json();
                csrf = csrfData.csrf;
                console.log("✅ CSRF token received");
            } else {
                console.warn("⚠️ Failed to fetch CSRF token, will fetch per-entry");
            }
        }

        for (let i = 0; i < toAdd.length; i++) {
            const item = toAdd[i];
            const food = item.selected;
            console.log(`\n➕ Adding item ${i + 1}/${toAdd.length}: ${food.name}`);
            await logFood(food.food_id, food.weight_id, item.parsed.quantity, csrf);

            if (i < toAdd.length - 1) {
                const delayMs = (Math.random() * 20 + 5) * 1000;
                const delaySec = (delayMs / 1000).toFixed(1);
                console.log(`⏳ Waiting ${delaySec}s before next entry...`);
                await new Promise(resolve => setTimeout(resolve, delayMs));
            }
        }

        console.log("\n✨ Batch operation completed successfully");
        foodInput.value = "";
        searchResults.style.display = "none";
        currentFoodItems = [];
        await loadToday();
    } catch (err) {
        console.error("❌ Batch operation error:", err);
        alert(`Error adding foods: ${err.message}`);
    } finally {
        addAllBtn.disabled = false;
        addAllBtn.textContent = "Add All to Diary";
    }
}

async function logFood(foodId, weightId, quantity, csrf = null) {
    if (!sessionId) return;

    try {
        const payload = {
            food_id: foodId,
            weight_id: weightId,
            quantity: quantity,
            meal: currentMeal,
        };

        if (csrf) {
            payload.csrf = csrf;
        }

        console.log(`\n📝 LOGGING FOOD: ID=${foodId}, Qty=${quantity}g, Meal=${currentMeal}`);
        console.log("📤 Request payload:", payload);

        const response = await fetch("/api/log", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${sessionId}`,
            },
            body: JSON.stringify(payload),
        });

        console.log("📥 Response status:", response.status, response.statusText);

        if (!response.ok) throw new Error("Failed to log food");

        const data = await response.json();
        console.log("📦 Response data:", data);
        console.log("✅ Food successfully logged");

        const key = `${foodId}_${Date.now()}`;
        entryDebugInfo[key] = data;
    } catch (err) {
        console.error("❌ Error logging food:", err);
        alert(`Error logging food: ${err.message}`);
    }
}

function parseInput(text) {
    // Parse "food 123" or "food 123g" format
    const match = text.trim().match(/^(.*?)\s+(\d+(?:\.\d+)?)\s*(\w*)$/);

    if (match) {
        return {
            name: match[1].trim(),
            quantity: parseFloat(match[2]),
            unit: match[3] || "g",
        };
    }

    // Fallback: search as-is with default quantity
    return {
        name: text,
        quantity: 100,
        unit: "g",
    };
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
