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
const refreshBtn = document.getElementById("refresh-btn");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    sessionId = localStorage.getItem("sessionId");
    if (sessionId) {
        showDashboard();
        loadToday();
    } else {
        showLogin();
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
        if (e.key === "Enter") handleSearch();
    });
    refreshBtn.addEventListener("click", loadToday);

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
        usernameInput.value = "";
        passwordInput.value = "";
    }
}

async function handleCookieLogin(e) {
    e.preventDefault();
    cookieError.textContent = "";

    const cookie = cookieInput.value.trim();

    if (!cookie) {
        cookieError.textContent = "Please paste your session cookie";
        return;
    }

    await performLogin({ cookie }, cookieError);

    if (sessionId) {
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
                li.innerHTML = `
                    <span class="entry-name">${escapeHtml(entry.name)}</span>
                    <span class="entry-calories">${Math.round(entry.calories || 0)} cal</span>
                `;
                entryList.appendChild(li);
            });
        }
    });

    // Clear search results
    searchResults.style.display = "none";
    resultsList.innerHTML = "";
    foodInput.value = "";
}

async function handleSearch() {
    const query = foodInput.value.trim();
    if (!query || !sessionId) return;

    const parsed = parseInput(query);

    try {
        const response = await fetch("/api/search", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${sessionId}`,
            },
            body: JSON.stringify({ query: parsed.name }),
        });

        if (!response.ok) throw new Error("Search failed");

        const data = await response.json();
        showResults(data.results || [], parsed.quantity);
    } catch (err) {
        alert(`Search error: ${err.message}`);
    }
}

function showResults(results, defaultQuantity) {
    resultsList.innerHTML = "";

    results.forEach((food) => {
        const div = document.createElement("div");
        div.className = "result-item";

        const calories = Math.round(food.calories || 0);
        const protein = food.protein ? Math.round(food.protein) : "?";
        const carbs = food.carbs ? Math.round(food.carbs) : "?";
        const fat = food.fat ? Math.round(food.fat) : "?";

        div.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div class="result-name">${escapeHtml(food.name)}</div>
                    <div class="result-meta">
                        <span>${calories} cal</span>
                        <span>P: ${protein}g</span>
                        <span>C: ${carbs}g</span>
                        <span>F: ${fat}g</span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <input type="number" class="quantity-input" value="${defaultQuantity}" min="0.1" step="0.1">
                    <button style="background: #667eea; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Add</button>
                </div>
            </div>
        `;

        const button = div.querySelector("button");
        const quantityInput = div.querySelector(".quantity-input");
        button.addEventListener("click", async () => {
            const quantity = parseFloat(quantityInput.value) || 1;
            await logFood(food.food_id, food.weight_id, quantity);
            loadToday();
        });

        resultsList.appendChild(div);
    });

    searchResults.style.display = "block";
}

async function logFood(foodId, weightId, quantity) {
    if (!sessionId) return;

    try {
        const response = await fetch("/api/log", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${sessionId}`,
            },
            body: JSON.stringify({
                food_id: foodId,
                weight_id: weightId,
                quantity: quantity,
                meal: currentMeal,
            }),
        });

        if (!response.ok) throw new Error("Failed to log food");
    } catch (err) {
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
