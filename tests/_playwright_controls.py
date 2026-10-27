from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8678"
ROUTES = [
    "/dashboard",
    "/core/plugin-management",
    "/core/terminal",
    "/llm_provider",
    "/log_manager",
    "/prime_backup",
    "/plugins/hello_world",
    "/user/management",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    bad_responses = []
    page.on("console", lambda m: errors.append(f"console:{m.type}:{m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror:{e}"))
    page.on("requestfailed", lambda r: errors.append(f"failed:{r.url}:{r.failure}"))
    page.on("response", lambda r: bad_responses.append((r.status, r.url)) if r.status >= 400 else None)

    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.locator("#userName_input").fill("root")
    page.locator("#password_input").fill("root")
    page.get_by_role("button", name="login").click()
    page.wait_for_timeout(800)
    assert "/login" not in page.url, page.url

    search = page.locator("input[placeholder]").first
    search.fill("dashboard")
    search.press("Enter")
    page.wait_for_timeout(250)
    print("SEARCH", page.url)

    for route in ROUTES:
        page.goto(f"{BASE}{route}", wait_until="networkidle")
        page.wait_for_timeout(500)
        visible_text = page.locator("body").inner_text()
        print("PAGE", route, "|", " | ".join(x.strip() for x in visible_text.splitlines() if x.strip())[:260])

        if route == "/dashboard":
            page.get_by_role("button", name="Refresh Data", exact=True).click()
            page.get_by_role("button", name="Terminal", exact=True).click()
            page.wait_for_timeout(250)
        elif route == "/core/plugin-management":
            page.get_by_role("button", name="Refresh", exact=True).first.click()
            rows = page.locator("tbody tr")
            print("PLUGIN_ROWS", rows.count())
            if rows.count():
                rows.first.click()
                page.wait_for_timeout(500)
                print("PLUGIN_DETAIL", page.locator("body").inner_text()[-260:].replace("\n", " | "))
        elif route == "/core/terminal":
            inputs = page.locator("input")
            if inputs.count():
                inputs.last.fill("!!help")
            page.get_by_role("button", name="Execute", exact=True).click()
        elif route == "/llm_provider":
            page.get_by_role("button", name="Refresh", exact=True).click()
            page.get_by_role("button", name="Run", exact=True).click()
        elif route == "/log_manager":
            page.get_by_role("button", name="Refresh", exact=True).click()
            page.get_by_role("button", name="Save", exact=True).click()
        elif route == "/prime_backup":
            page.get_by_role("button", name="Create Backup", exact=True).click()
            page.get_by_role("button", name="OK", exact=True).click()
            page.wait_for_timeout(250)
            page.get_by_role("button", name="Cancel", exact=True).first.click()
        elif route == "/plugins/hello_world":
            page.locator("input[placeholder='Type a name']").fill("Playwright")
            page.get_by_role("button", name="Go", exact=True).click()
        elif route == "/user/management":
            page.get_by_role("button", name="Create User", exact=True).click()
            page.get_by_role("button", name="Cancel", exact=True).click()

        page.wait_for_timeout(400)

    print("BAD_RESPONSES", bad_responses)
    print("ERRORS", errors)
    browser.close()
