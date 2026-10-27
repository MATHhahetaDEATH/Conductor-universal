use serde::Deserialize;

#[derive(Deserialize)]
struct LoginResponse {
    status: Option<String>,
    token: Option<String>,
    msg: Option<String>,
}

fn normalize_server(value: &str) -> String {
    let mut base = value.trim().trim_end_matches('/').to_string();
    if !base.starts_with("http://") && !base.starts_with("https://") {
        base = format!("http://{base}");
    }
    let host = base.split_once("://").map(|(_, rest)| rest).unwrap_or(&base);
    if !host.split('/').next().unwrap_or(host).contains(':') {
        base.push_str(":8678");
    }
    base
}

#[tauri::command]
async fn login(server: String, username: String, password: String) -> Result<String, String> {
    let base = normalize_server(&server);
    let response = reqwest::Client::new()
        .post(format!("{base}/api/user/login"))
        .json(&serde_json::json!({ "userName": username, "password": password }))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    let status = response.status();
    let payload: LoginResponse = response.json().await.map_err(|error| error.to_string())?;
    if status.is_success() && payload.status.as_deref() == Some("ok") {
        return payload.token.ok_or_else(|| "Login response did not include a token".to_string());
    }
    Err(payload.msg.unwrap_or_else(|| format!("Login failed ({status})")))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![login])
        .run(tauri::generate_context!())
        .expect("error while running Conductor Mobile");
}
