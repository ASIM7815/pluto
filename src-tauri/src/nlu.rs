//! PLUTO deterministic intent planner (NLU).
//!
//! Port of the original Python `app/agent/nlu.py` IntentPlanner: turns a
//! natural-language command into an ordered list of real tool calls plus
//! conversational text. Runs fully on-device in Rust - no external AI/API.

use regex::Regex;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NluStep {
    pub name: String,
    #[serde(default)]
    pub arguments: serde_json::Value,
}

#[derive(Debug, Clone)]
pub enum PlanItem {
    Step(NluStep),
    Text(String),
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SessionContext {
    pub recent_files: Vec<String>,
    pub current_directory: Option<String>,
    pub current_url: Option<String>,
    pub selected_result_index: Option<u32>,
    pub current_app: Option<String>,
    /// Last search engine/platform used (google, youtube, bing, ...), so a
    /// bare follow-up like "search Avengers" keeps searching the same site.
    #[serde(default)]
    pub last_search_engine: Option<String>,
}

pub const PLANNED_TOOL_NAMES: &[&str] = &[
    "open_browser",
    "open_application",
    "close_application",
    "switch_to_application",
    "list_running_applications",
    "open_file",
    "open_folder",
    "find_files",
    "create_folder",
    "create_file",
    "read_file",
    "list_directory",
    "delete_file",
    "move_file",
    "copy_file",
    "take_screenshot",
    "set_volume",
    "get_volume",
    "copy_to_clipboard",
    "get_clipboard",
    "get_processes",
    "kill_process",
    "open_url",
    "browser_search",
    "browser_click",
    "browser_key",
    "browser_snapshot",
    "close_browser",
    "send_message",
    "open_chat_app",
    "execute_command",
];

const DIR_ALIASES: &[(&str, &str)] = &[
    ("the documents folder", "~/Documents"),
    ("desktop", "~/Desktop"),
    ("documents", "~/Documents"),
    ("document", "~/Documents"),
    ("docs", "~/Documents"),
    ("downloads", "~/Downloads"),
    ("download", "~/Downloads"),
    ("pictures", "~/Pictures"),
    ("photos", "~/Pictures"),
    ("picture", "~/Pictures"),
    ("music", "~/Music"),
    ("videos", "~/Videos"),
    ("video", "~/Videos"),
    ("movies", "~/Videos"),
    ("projects", "~/Projects"),
    ("project", "~/Projects"),
    ("home folder", "~"),
    ("home directory", "~"),
    ("home", "~"),
];

const SITE_URLS: &[(&str, &str)] = &[
    ("youtube", "https://www.youtube.com"),
    ("yt", "https://www.youtube.com"),
    ("google", "https://www.google.com"),
    ("gmail", "https://mail.google.com"),
    ("google drive", "https://drive.google.com"),
    ("github", "https://github.com"),
    ("stackoverflow", "https://stackoverflow.com"),
    ("stack overflow", "https://stackoverflow.com"),
    ("reddit", "https://www.reddit.com"),
    ("twitter", "https://twitter.com"),
    ("x", "https://twitter.com"),
    ("facebook", "https://www.facebook.com"),
    ("instagram", "https://www.instagram.com"),
    ("wikipedia", "https://www.wikipedia.org"),
    ("amazon", "https://www.amazon.com"),
    ("netflix", "https://www.netflix.com"),
    ("spotify", "https://open.spotify.com"),
    ("chatgpt", "https://chat.openai.com"),
    ("openai", "https://openai.com"),
    ("linkedin", "https://www.linkedin.com"),
    ("maps", "https://maps.google.com"),
    ("duckduckgo", "https://duckduckgo.com"),
    ("whatsapp", "https://web.whatsapp.com"),
];

const APP_MAPPINGS: &[(&str, &str)] = &[
    ("firefox", "firefox"),
    ("chrome", "google-chrome"),
    ("google chrome", "google-chrome"),
    ("chromium", "chromium"),
    ("brave", "brave-browser"),
    ("edge", "microsoft-edge"),
    ("vscode", "code"),
    ("vs code", "code"),
    ("visual studio code", "code"),
    ("code", "code"),
    ("sublime", "subl"),
    ("sublime text", "subl"),
    ("vim", "vim"),
    ("emacs", "emacs"),
    ("files", "nautilus"),
    ("file manager", "nautilus"),
    ("dolphin", "dolphin"),
    ("thunar", "thunar"),
    ("terminal", "gnome-terminal"),
    ("konsole", "konsole"),
    ("xterm", "xterm"),
    ("alacritty", "alacritty"),
    ("gnome terminal", "gnome-terminal"),
    ("slack", "slack"),
    ("discord", "discord"),
    ("telegram", "telegram-desktop"),
    ("whatsapp", "whatsapp-for-linux"),
    ("zoom", "zoom"),
    ("libreoffice", "libreoffice"),
    ("writer", "libreoffice"),
    ("calc", "libreoffice"),
    ("gimp", "gimp"),
    ("inkscape", "inkscape"),
    ("obs", "obs"),
    ("calculator", "gnome-calculator"),
    ("settings", "gnome-control-center"),
    ("control center", "gnome-control-center"),
    ("vlc", "vlc"),
    ("spotify", "spotify"),
    ("audacity", "audacity"),
];

const KNOWN_WEBSITES: &[(&str, &str)] = &[
    ("youtube", "https://www.youtube.com"),
    ("gmail", "https://mail.google.com"),
    ("google mail", "https://mail.google.com"),
    ("google drive", "https://drive.google.com"),
    ("drive", "https://drive.google.com"),
    ("google docs", "https://docs.google.com"),
    ("docs", "https://docs.google.com"),
    ("google sheets", "https://docs.google.com/spreadsheets"),
    ("sheets", "https://docs.google.com/spreadsheets"),
    ("google slides", "https://docs.google.com/presentation"),
    ("slides", "https://docs.google.com/presentation"),
    ("github", "https://github.com"),
    ("stackoverflow", "https://stackoverflow.com"),
    ("stack overflow", "https://stackoverflow.com"),
    ("reddit", "https://www.reddit.com"),
    ("twitter", "https://twitter.com"),
    ("x", "https://twitter.com"),
    ("facebook", "https://www.facebook.com"),
    ("instagram", "https://www.instagram.com"),
    ("linkedin", "https://www.linkedin.com"),
    ("amazon", "https://www.amazon.com"),
    ("netflix", "https://www.netflix.com"),
    ("spotify web", "https://open.spotify.com"),
    ("whatsapp web", "https://web.whatsapp.com"),
    ("chatgpt", "https://chat.openai.com"),
    ("chat gpt", "https://chat.openai.com"),
    ("openai", "https://openai.com"),
    ("notion", "https://www.notion.so"),
    ("figma", "https://www.figma.com"),
    ("canva", "https://www.canva.com"),
    ("trello", "https://trello.com"),
    ("asana", "https://app.asana.com"),
    ("miro", "https://miro.com"),
];

/// Deterministic search-engine table: alias -> (engine id, search base URL).
const SEARCH_ENGINES: &[(&str, &str, &str)] = &[
    ("you tube", "youtube", "https://www.youtube.com/results?search_query="),
    ("duck duck go", "duckduckgo", "https://duckduckgo.com/?q="),
    ("google", "google", "https://www.google.com/search?q="),
    ("youtube", "youtube", "https://www.youtube.com/results?search_query="),
    ("bing", "bing", "https://www.bing.com/search?q="),
    ("duckduckgo", "duckduckgo", "https://duckduckgo.com/?q="),
    ("ddg", "duckduckgo", "https://duckduckgo.com/?q="),
    ("github", "github", "https://github.com/search?q="),
    ("reddit", "reddit", "https://www.reddit.com/search?q="),
    ("wikipedia", "wikipedia", "https://en.wikipedia.org/w/index.php?search="),
    ("amazon", "amazon", "https://www.amazon.com/s?k="),
    ("the web", "google", "https://www.google.com/search?q="),
    ("the internet", "google", "https://www.google.com/search?q="),
    ("yt", "youtube", "https://www.youtube.com/results?search_query="),
];

/// Engine homepage used when the user only says "open <engine>".
fn engine_home(engine: &str) -> &'static str {
    match engine {
        "youtube" => "https://www.youtube.com",
        "duckduckgo" => "https://duckduckgo.com",
        "bing" => "https://www.bing.com",
        "github" => "https://github.com",
        "reddit" => "https://www.reddit.com",
        "wikipedia" => "https://www.wikipedia.org",
        "amazon" => "https://www.amazon.com",
        _ => "https://www.google.com",
    }
}

/// Verbs that start a web search (longest first so "search for" wins).
const SEARCH_VERBS: &[&str] = &[
    "can you search for",
    "could you search for",
    "please search for",
    "search for",
    "search the web for",
    "look up",
    "look for",
    "google",
    "search",
    "find",
    "play",
    "watch",
    "show me",
];

const GREETING_WORDS: &[&str] = &[
    "hello", "hi ", "hey", "yo ", "good morning", "good afternoon", "good evening", "howdy", "hiya",
];
const THANKS_WORDS: &[&str] = &[
    "thank", "thanks", "appreciate", "good job", "great job", "nice work", "awesome",
    "well done", "much obliged",
];
const SCREENSHOT_PHRASES: &[&str] = &[
    "screenshot", "screen shot", "screen capture", "capture the screen", "capture my screen",
    "capture a screenshot", "capture the screen to", "take a screenshot", "take screenshot",
    "snapshot of the screen", "snapshot the screen", "screen grab", "grab a screenshot",
    "print screen", "printscreen", "capture screen", "grab the screen", "take a screen capture",
];
const SCREENSHOT_AREA_WINDOW: &[&str] = &["window", "active window", "this window", "current window"];
const SCREENSHOT_AREA_SELECT: &[&str] = &[
    "select", "selection", "region", "a part of the screen", "part of the screen",
    "area of the screen", "an area",
];

fn norm(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ").to_lowercase()
}

fn words(value: &str) -> String {
    format!(" {} ", norm(value))
}

fn has(text: &str, subs: &[&str]) -> bool {
    let t = norm(text);
    subs.iter().any(|s| t.contains(s))
}

fn has_any_relaxed(text: &str, subs: &[&str]) -> bool {
    subs.iter().any(|s| text.to_lowercase().contains(s))
}

fn dir_from_text(text: &str, default: &str) -> String {
    let re = Regex::new(r"(?:/|~/)[\w./~-]+").unwrap();
    if let Some(m) = re.find(text) {
        let raw = m.as_str();
        if !raw.starts_with('~') {
            return raw.trim_end_matches('/').to_string();
        }
        return expand_home(raw.trim_end_matches('/'));
    }
    let t = norm(text);
    let mut best: Option<(usize, String)> = None;
    for (alias, path) in DIR_ALIASES {
        if t.contains(alias) && best.as_ref().map(|(len, _)| alias.len() > *len).unwrap_or(true) {
            best = Some((alias.len(), expand_home(path)));
        }
    }
    best.map(|(_, p)| p).unwrap_or_else(|| expand_home(default))
}

pub fn expand_home(path: &str) -> String {
    if path == "~" {
        return dirs::home_dir().map(|p| p.display().to_string()).unwrap_or_else(|| path.to_string());
    }
    if let Some(rest) = path.strip_prefix("~/") {
        if let Some(home) = dirs::home_dir() {
            return format!("{}/{}", home.display(), rest);
        }
    }
    path.to_string()
}

fn file_name_from(text: &str) -> Option<String> {
    // Quoted name first.
    let re_q = Regex::new(r#"["']([^"']+)["']"#).unwrap();
    if let Some(m) = re_q.find(text) {
        let inner = m.as_str().trim_matches(|c| c == '"' || c == '\'');
        return Some(inner.trim().to_string());
    }
    // Called/named ...
    let re = Regex::new(
        r"(?i)(?:called|named)\s+([A-Za-z0-9_.\- ]+?)(?:\s+(?:in|inside|under|on|at|to|for|please|and|then|saying|containing|with|that|,)|$)",
    )
    .unwrap();
    if let Some(caps) = re.captures(text) {
        let name = caps.get(1).map(|m| m.as_str().trim().trim_end_matches('.').to_string())?;
        let lower = name.to_lowercase();
        if lower != "a folder"
            && lower != "folder"
            && lower != "the folder"
            && lower != "a file"
            && lower != "file"
            && lower != "the file"
            && lower != "new folder"
            && lower != "new file"
        {
            return Some(name);
        }
    }
    None
}

fn file_content(text: &str) -> String {
    let re_q = Regex::new(r#"["'](.+?)["']"#).unwrap();
    if let Some(m) = re_q.captures(text) {
        return m.get(1).unwrap().as_str().trim().to_string();
    }
    let t = text.to_lowercase();
    for marker in ["saying ", "containing ", "with content ", "with the text ", "that says ", "reading "] {
        if let Some(idx) = t.find(marker) {
            let start = idx + marker.len();
            return text[start..].trim_matches(|c: char| c == ' ' || c == '.' || c == ',' || c == ';').to_string();
        }
    }
    String::new()
}

fn clipboard_text(text: &str) -> String {
    let re_q = Regex::new(r#"["'](.+?)["']"#).unwrap();
    if let Some(m) = re_q.captures(text) {
        return m.get(1).unwrap().as_str().trim().to_string();
    }
    let t = text.to_lowercase();
    for marker in ["copy ", "put ", "set ", "save ", "store ", "add ", "send "] {
        if let Some(idx) = t.find(marker) {
            let mut rest = &text[idx + marker.len()..];
            for stop in [
                " to the clipboard", " on the clipboard", " onto the clipboard",
                " to clipboard", " on clipboard", " into the clipboard",
            ] {
                if let Some(pos) = rest.to_lowercase().find(stop) {
                    rest = &rest[..pos];
                    break;
                }
            }
            let cleaned = rest.trim().trim_end_matches(|c: char| c == ' ' || c == ',' || c == '.' || c == ';' || c == ':' || c == '!').to_string();
            if !cleaned.is_empty() {
                return cleaned;
            }
        }
    }
    String::new()
}

fn screenshot_area(text: &str) -> String {
    let t = norm(text);
    if SCREENSHOT_AREA_WINDOW.iter().any(|k| t.contains(k)) {
        return "window".to_string();
    }
    if SCREENSHOT_AREA_SELECT.iter().any(|k| t.contains(k)) {
        return "select".to_string();
    }
    "full".to_string()
}

fn site_from_url(url: &str) -> String {
    let lower = url.to_lowercase();
    if lower.contains("youtube.com") || lower.contains("youtu.be") {
        return "youtube".into();
    }
    if lower.contains("github.com") { return "github".into(); }
    if lower.contains("reddit.com") { return "reddit".into(); }
    if lower.contains("wikipedia.org") { return "wikipedia".into(); }
    if lower.contains("amazon") { return "amazon".into(); }
    if lower.contains("google.com/search") || lower.contains("google.") { return "google".into(); }
    if lower.contains("duckduckgo.com") { return "duckduckgo".into(); }
    if lower.contains("bing.com") { return "bing".into(); }
    String::new()
}

/// Word-boundary aware match: single-letter / short aliases (e.g. "x" for
/// Twitter) must not match inside longer words ("example").
fn word_match(text: &str, key: &str) -> bool {
    if key.len() <= 2 {
        Regex::new(&format!(r"\b{}\b", regex::escape(key)))
            .map(|re| re.is_match(text))
            .unwrap_or(false)
    } else {
        text.contains(key)
    }
}

fn site_keyword(rest: &str) -> Option<String> {
    let r = norm(rest);
    for (key, _) in SITE_URLS.iter().rev() {
        if word_match(&r, key) {
            return Some((*key).to_string());
        }
    }
    None
}

fn normalize_url(text: &str) -> String {
    let text = text.trim();
    if text.starts_with("http://") || text.starts_with("https://") {
        return text.to_string();
    }
    let lower = text.to_lowercase();
    for (site, url) in SITE_URLS {
        if site.len() <= 2 {
            if Regex::new(&format!(r"\b{}\b", regex::escape(site))).map(|re| re.is_match(&lower)).unwrap_or(false) {
                return url.to_string();
            }
        } else if lower.contains(site) {
            return url.to_string();
        }
    }
    if text.contains('.') && !text.contains(' ') {
        return format!("https://{}", text);
    }
    let mut query = String::new();
    let mut first = true;
    for part in text.split_whitespace() {
        if !first { query.push('+'); }
        query.push_str(&part.replace(' ', "+").replace('%', "%25"));
        first = false;
    }
    format!("https://www.google.com/search?q={}", query)
}

pub fn app_alias(text: &str) -> Option<String> {
    let t = norm(text);
    let mut best: Option<(usize, &str)> = None;
    for (alias, executable) in APP_MAPPINGS {
        let matched = if alias.len() <= 2 {
            Regex::new(&format!(r"\b{}\b", regex::escape(alias)))
                .map(|re| re.is_match(&t))
                .unwrap_or(false)
        } else {
            t.contains(alias)
        };
        if matched && best.map(|(len, _)| alias.len() > len).unwrap_or(true) {
            best = Some((alias.len(), executable));
        }
    }
    best.map(|(_, exe)| exe.to_string())
}

fn is_app_or_site_ref(cmd: &str) -> bool {
    let w = norm(cmd.trim().trim_matches(|c| c == '\'' || c == '"'));
    if w.is_empty() {
        return false;
    }
    if app_alias(&w).is_some() {
        return true;
    }
    if KNOWN_WEBSITES.iter().any(|(k, _)| word_match(&w, k)) {
        return true;
    }
    SITE_URLS.iter().any(|(k, _)| word_match(&w, k))
}

fn resolve_candidate(name: &str, ctx: &SessionContext) -> String {
    if name.is_empty() {
        return String::new();
    }
    if name.starts_with('~') || name.starts_with('/') {
        return expand_home(name);
    }
    for recent in &ctx.recent_files {
        if recent.rsplit('/').next().unwrap_or("") == name {
            return recent.clone();
        }
    }
    for folder in ["~/Documents", "~/Downloads", "~/Desktop", "~/Projects", "~/Pictures", "~"] {
        let candidate = format!("{}/{}", expand_home(folder), name);
        if std::path::Path::new(&candidate).exists() {
            return candidate;
        }
    }
    if let Some(base) = &ctx.current_directory {
        return format!("{}/{}", base, name);
    }
    format!("{}/{}", expand_home("~/Documents"), name)
}

/// Returns ordered plan (steps + conversational strings).
pub fn plan(user_text: &str, ctx: &SessionContext) -> Vec<PlanItem> {
    let text = user_text.trim();
    if text.is_empty() {
        return vec![PlanItem::Text("I didn't catch that - try again, BOSS.".into())];
    }
    let plan = route(text, ctx);
    if plan.is_empty() {
        return vec![PlanItem::Text(capabilities_reply())];
    }
    plan.into_iter()
        .map(|item| match &item {
            PlanItem::Step(s) if !PLANNED_TOOL_NAMES.contains(&s.name.as_str()) => {
                PlanItem::Text(format!("I can't run '{}' yet, BOSS.", s.name))
            }
            other => other.clone(),
        })
        .collect()
}

pub fn recommend(user_text: &str, ctx: &SessionContext) -> Vec<String> {
    let mut seen = Vec::new();
    for item in plan(user_text, ctx) {
        if let PlanItem::Step(s) = item {
            if !seen.contains(&s.name) {
                seen.push(s.name);
            }
        }
    }
    seen
}

fn route(text: &str, ctx: &SessionContext) -> Vec<PlanItem> {
    let t = norm(text);
    let w = words(text);

    // 0) silence
    if ["go silent", "stop listening", "be quiet"].iter().any(|k| t.contains(k)) {
        return vec![PlanItem::Text("Going silent. I'll be here if you need me, BOSS.".into())];
    }

    // 1) Screenshots
    if SCREENSHOT_PHRASES.iter().any(|k| t.contains(k))
        || (has(text, &["take", "capture", "grab", "print", "shoot"])
            && has(text, &["screenshot", "screen", "screen shot"]))
    {
        let area = screenshot_area(text);
        let mut args = serde_json::json!({ "area": area });
        let mut folder = dir_from_text(text, "");
        if folder.is_empty() {
            folder = String::new();
        }
        if has(text, &["save", "store", "put", "keep"]) || !folder.is_empty() {
            let dir = if folder.is_empty() { expand_home("~/Pictures") } else { folder.clone() };
            args["directory"] = serde_json::json!(dir);
        }
        if let Some(caps) = Regex::new(r"(?i)\bas\s+([\w\- .]+?)(?:\.\s|$)").unwrap().captures(text) {
            let name = caps.get(1).unwrap().as_str().trim();
            if Regex::new(r"(?i)\.(png|jpe?g|webp)$").unwrap().is_match(name) {
                args["filename"] = serde_json::json!(name);
            }
        }
        let where_msg = args.get("directory").and_then(|v| v.as_str()).map(|s| s.to_string()).unwrap_or_default();
        let msg = if where_msg.is_empty() {
            "Taking a screenshot, BOSS.".to_string()
        } else {
            format!("Taking a screenshot saved to {}, BOSS.", where_msg)
        };
        return vec![
            PlanItem::Step(NluStep { name: "take_screenshot".into(), arguments: args }),
            PlanItem::Text(msg),
        ];
    }

    // 2) Volume / mute
    if has(text, &["volume", "sound", "audio", "mute", "unmute"])
        || (has(text, &["loud", "louder", "quieter"])
            && has(text, &["too", "set", "turn", "make it", "down", "up"]))
    {
        if ["unmute", "sound back on", "turn the sound on", "audio on", "un-mute", "un mute"]
            .iter().any(|k| t.contains(k))
        {
            return vec![
                PlanItem::Step(NluStep { name: "set_volume".into(), arguments: serde_json::json!({"level": "unmute"}) }),
                PlanItem::Text("Audio unmuted, BOSS.".into()),
            ];
        }
        if ["mute", "muted", "silence the sound", "turn off sound", "sound off",
            "turn the sound off", "no sound", "mute audio"].iter().any(|k| t.contains(k))
        {
            return vec![
                PlanItem::Step(NluStep { name: "set_volume".into(), arguments: serde_json::json!({"level": "mute"}) }),
                PlanItem::Text("Audio muted, BOSS.".into()),
            ];
        }
        if let Some(caps) = Regex::new(r"(\d{1,3})\s*%?").unwrap().captures(&t) {
            let level = caps.get(1).unwrap().as_str().parse::<u32>().unwrap_or(50).min(100);
            return vec![
                PlanItem::Step(NluStep { name: "set_volume".into(), arguments: serde_json::json!({"level": level}) }),
                PlanItem::Text(format!("Volume set to {}%, BOSS.", level)),
            ];
        }
        if ["what", "how loud", "current", "get ", "read ", "show", "check"].iter().any(|k| t.contains(k)) {
            return vec![
                PlanItem::Step(NluStep { name: "get_volume".into(), arguments: serde_json::json!({}) }),
                PlanItem::Text("Reading the current volume, BOSS.".into()),
            ];
        }
        return vec![PlanItem::Text(
            "I can set the volume to a specific level (e.g. \"set volume to 40\") or mute/unmute the audio, BOSS. What level do you want?".into(),
        )];
    }

    // 3) Clipboard
    if t.contains("clipboard") || t.contains("clip board") {
        let is_copy = ["copy", "put", "set", "save", "store", "add", "send"].iter().any(|k| t.contains(k));
        let is_read = ["what", "read", "get", "show", "contents", "paste", "fetch"].iter().any(|k| t.contains(k));
        if is_copy && !is_read {
            let payload = clipboard_text(text);
            return vec![
                PlanItem::Step(NluStep { name: "copy_to_clipboard".into(), arguments: serde_json::json!({ "text": payload }) }),
                PlanItem::Text("Copied to the clipboard, BOSS.".into()),
            ];
        }
        return vec![
            PlanItem::Step(NluStep { name: "get_clipboard".into(), arguments: serde_json::json!({}) }),
            PlanItem::Text("Reading the clipboard, BOSS.".into()),
        ];
    }

    // 4) Greetings / social / meta
    if let Some(greeting) = greeting_plan(text, &t, &w) {
        return greeting;
    }

    // 5) System status & process checks
    if let Some(sys) = system_plan(text, &t, &w) {
        return sys;
    }

    // 6) Browser & website intents
    if let Some(browser) = browser_plan(text, &t, &w, ctx) {
        return browser;
    }

    // 7) File operations
    if let Some(files) = file_plan(text, &t, &w, ctx) {
        return files;
    }

    // 8) Messaging
    if let Some(msg) = messaging_plan(text, &t) {
        return msg;
    }

    // 9) Terminal command
    if let Some(term) = terminal_plan(text, &t) {
        return term;
    }

    // 10) Applications
    if let Some(apps) = application_plan(text, &t, &w) {
        return apps;
    }

    // 11) Explicit URL
    if let Some(caps) = Regex::new(r"(?i)https?://\S+").unwrap().captures(text) {
        let url = caps.get(0).unwrap().as_str().trim_end_matches(|c| c == '.' || c == ',' || c == ';' || c == '!' || c == '?');
        return vec![
            PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
            PlanItem::Text(format!("Opening {}, BOSS.", url)),
        ];
    }

    vec![]
}

fn greeting_plan(text: &str, t: &str, w: &str) -> Option<Vec<PlanItem>> {
    if [" who are you ", " what are you ", " introduce yourself ", " your name ", " what is your name "]
        .iter().any(|k| w.contains(k))
    {
        return Some(vec![PlanItem::Text(
            "I'm PLUTO, your autonomous Linux desktop assistant. I run real tools on this machine - applications, browser automation, files, screenshots, system control - and verify each action before I report back.".into(),
        )]);
    }
    if THANKS_WORDS.iter().any(|k| t.contains(k)) {
        return Some(vec![PlanItem::Text("You're welcome, BOSS! What would you like me to do next?".into())]);
    }
    if ["what can you do", "help", "capabilities", "what tools", "your features", "show commands", "list your skills"]
        .iter().any(|k| t.contains(k))
    {
        return Some(vec![PlanItem::Text(capabilities_reply())]);
    }
    let bare = t == "hi" || t == "hey" || t == "yo" || t == "sup" || t == "hiya" || t == "hello" || t == "howdy" || t == "what's up" || t == "whats up";
    if bare
        || (GREETING_WORDS.iter().any(|g| t.starts_with(g.trim_end()))
            && !["open", "search", "play", "create", "send", "delete", "move", "copy", "close",
                "run", "take", "set", "read", "find", "list", "screenshot", "show", "mute",
                "quit", "kill", "start", "launch", "type", "scroll", "click", "zoom", "install"]
                .iter().any(|k| t.contains(k)))
    {
        return Some(vec![PlanItem::Text(
            "Hello BOSS! I'm PLUTO, your autonomous Linux desktop assistant. I can open apps and websites, search and browse, manage files, take screenshots, control volume and clipboard, check the system and run commands. What do you need?".into(),
        )]);
    }
    if [" how are you", " how's it going", " hows it going", " how are things"].iter().any(|k| w.contains(k)) {
        return Some(vec![PlanItem::Text("Running smoothly, BOSS! What can I do for you?".into())]);
    }
    None
}

fn capabilities_reply() -> String {
    "Here's what I can do, BOSS: open and close apps, browse and search (YouTube, Google, websites), create/read/copy/move/delete files and folders, take screenshots, control volume and the clipboard, check running processes, and run terminal commands with your approval.".to_string()
}

pub fn capabilities_reply_public() -> String {
    capabilities_reply()
}

fn system_plan(text: &str, t: &str, w: &str) -> Option<Vec<PlanItem>> {
    let status_phrases = [
        "system status", "system stats", "system health", "system info", "system information",
        "performance", "optimize", "cpu usage", "memory usage", "ram usage", "disk usage",
        "disk space", "task manager", "process list", "running processes", "top processes",
        "what's running", "what is running", "list processes", "show processes", "see processes",
        "processes running",
    ];
    if status_phrases.iter().any(|k| t.contains(k)) {
        let limit = if ["top", "list", "show", "see"].iter().any(|k| t.contains(k)) { 15 } else { 8 };
        return Some(vec![
            PlanItem::Step(NluStep { name: "get_processes".into(), arguments: serde_json::json!({ "limit": limit }) }),
            PlanItem::Text("Here's what's running on the system, BOSS.".into()),
        ]);
    }
    let running_re = Regex::new(r"(?:is|are)\s+([a-z0-9_.-]{1,40}?)\s+running\??$").unwrap();
    let check_re = Regex::new(r"(?:check|see|tell me)\s+if\s+([a-z0-9_.-]{1,40}?)\s+(?:is\s+)?running").unwrap();
    let name = running_re.captures(t)
        .or_else(|| check_re.captures(t))
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().trim().to_string());
    if let Some(name) = name {
        if !["which", "what", "list"].iter().any(|k| t.contains(k))
            && !["it", "this", "that"].contains(&name.as_str())
        {
            return Some(vec![
                PlanItem::Step(NluStep { name: "get_processes".into(), arguments: serde_json::json!({ "name": name, "limit": 10 }) }),
                PlanItem::Text(format!("Checking whether {} is running, BOSS.", name)),
            ]);
        }
    }
    let kill_verbs = [" kill ", " stop ", " end ", " terminate "].iter().any(|k| w.contains(k));
    if kill_verbs && ["process", "task", "application", "program", "app "].iter().any(|k| t.contains(k)) {
        let kill_re = Regex::new(
            r"(?:kill|stop|end|terminate)\s+(?:the\s+)?(?:process|task|application|program|app)?\s*(?:named|called|name)?\s*([a-z0-9_.-]{2,40}?)\s*$",
        ).unwrap();
        let mut target = kill_re.captures(t).and_then(|c| c.get(1)).map(|m| m.as_str().trim().to_string()).unwrap_or_default();
        target = Regex::new(r"\s+(process|task|application|program|app)$")
            .unwrap().replace(&target, "").to_string();
        if !target.is_empty() && !["it", "that", "this", "everything", "all", "a", "the"].contains(&target.as_str()) {
            return Some(vec![
                PlanItem::Step(NluStep { name: "kill_process".into(), arguments: serde_json::json!({ "process": target }) }),
                PlanItem::Text(format!("Stopping {}, BOSS.", target)),
            ]);
        }
    }
    None
}

/// Whole-word file nouns that signal a *file* command rather than a web
/// search ("find my files", "search for a document").
const FILE_WORDS: &[&str] = &["file", "files", "folder", "folders", "document", "documents", "pdf", "note"];

/// Common web TLDs used to decide that "open <name>.<tld>" is a website and
/// not a local file ("notes.txt" keeps routing to the file tools).
const WEB_TLDS: &[&str] = &[
    "com", "org", "net", "io", "ai", "dev", "app", "co", "me", "info", "edu", "gov", "tv", "xyz",
    "site", "online", "tech", "store", "cloud", "blog", "uk", "de", "fr", "ca", "au", "in", "jp",
    "ru", "br", "nl", "es", "it", "ch", "se", "pl", "be", "at", "no", "dk", "fi", "pt", "gr", "tr",
    "za", "mx", "ar", "kr", "cn", "tw", "hk", "sg", "nz", "ie", "il", "ae", "sa", "us", "eu",
];

struct ParsedSearch {
    engine: String,
    query: String,
    action: &'static str,
}

fn contains_word(text: &str, word: &str) -> bool {
    Regex::new(&format!(r"\b{}\b", regex::escape(word)))
        .map(|re| re.is_match(text))
        .unwrap_or(false)
}

fn url_encode_query(query: &str) -> String {
    let mut out = String::with_capacity(query.len());
    for b in query.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(b as char),
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

fn engine_for_alias(alias: &str) -> Option<(&'static str, &'static str)> {
    SEARCH_ENGINES
        .iter()
        .find(|(a, _, _)| *a == alias)
        .map(|(_, engine, base)| (*engine, *base))
}

fn engine_display(engine: &str) -> &'static str {
    match engine {
        "youtube" => "YouTube",
        "duckduckgo" => "DuckDuckGo",
        "bing" => "Bing",
        "github" => "GitHub",
        "reddit" => "Reddit",
        "wikipedia" => "Wikipedia",
        "amazon" => "Amazon",
        _ => "Google",
    }
}

fn engine_search_url(engine: &str, query: &str) -> String {
    let base = SEARCH_ENGINES
        .iter()
        .find(|(_, e, _)| *e == engine)
        .map(|(_, _, base)| *base)
        .unwrap_or("https://www.google.com/search?q=");
    format!("{}{}", base, url_encode_query(query))
}

/// Detect an explicit search-platform mention and strip it (plus its
/// connector) from the text. Examples: "on YouTube", "using Bing",
/// "Google Iron Man", "search YouTube for Iron Man".
fn extract_engine(text: &str) -> Option<(String, String)> {
    let t = norm(text);
    let mut aliases: Vec<&str> = SEARCH_ENGINES.iter().map(|(a, _, _)| *a).collect();
    aliases.sort_by_key(|a| std::cmp::Reverse(a.len()));
    aliases.dedup();

    for alias in aliases {
        let (engine, _) = engine_for_alias(alias).expect("alias lookup");
        let escaped = regex::escape(alias);
        // Pattern 1: "... <connector> [the] <alias>"  (platform mention)
        let pat_after = Regex::new(&format!(r"\b(?:on|in|using|via|at|within|over)\s+(?:the\s+|website\s+|site\s+)?{}", escaped)).ok()?;
        // Pattern 2: "<search verb> <alias> [for|about]..." (target form)
        let pat_verb = Regex::new(&format!(r"\b(?:search|find|look|watch|play|open|visit)\s+{}(?:\s+for\s+|\s+about\s+|\s+|\b)", escaped)).ok()?;
        // Pattern 3: leading alias as the verb ("Google Iron Man").
        let pat_leading = Regex::new(&format!(r"^{}\s+", escaped)).ok()?;

        let try_remove = |re: &Regex, strip_connector: bool| -> Option<(String, String)> {
            let m = re.find(&t)?;
            let mut start = m.start();
            let mut end = m.end();
            if end < t.len() {
                let next = t[end..].chars().next()?;
                // "youtube.com" must not be split into an engine mention.
                if next == '.' || next.is_alphanumeric() {
                    return None;
                }
            }
            if strip_connector {
                // Include the leading connector word (" on youtube").
                let before = &t[..start];
                if let Some(space) = before.rfind(' ') {
                    let word = before[space + 1..].trim();
                    let connector = ["on", "in", "using", "via", "at", "within", "over", "the", "website", "site"];
                    let mut drop = space;
                    if connector.contains(&word) {
                        drop = before[..space].rfind(' ').map(|i| i + 1).unwrap_or(0);
                    }
                    start = drop;
                } else {
                    start = 0;
                }
            }
            let removed = format!("{} {}", &t[..start], &t[end..]);
            Some((engine.to_string(), norm(&removed)))
        };

        for pat in [(&pat_after, true), (&pat_verb, false), (&pat_leading, false)] {
            if let Some(found) = try_remove(pat.0, pat.1) {
                return Some(found);
            }
        }
    }
    None
}

fn clean_query(raw: &str) -> String {
    let mut q = norm(raw);
    let mut guard = 0;
    loop {
        guard += 1;
        if guard > 12 {
            break;
        }
        let trimmed = q.trim();
        let mut changed = false;
        for stop in ["please", "now", "then", "also", "for", "about", "me", "us", "the", "a", "an", "to", "and"] {
            let prefix = format!("{} ", stop);
            if trimmed.starts_with(&prefix) {
                q = trimmed[prefix.len()..].to_string();
                changed = true;
                break;
            }
            if trimmed == stop {
                q = String::new();
                changed = true;
                break;
            }
        }
        if !changed {
            break;
        }
    }
    q.trim()
        .trim_matches(|c: char| c == ' ' || c == ',' || c == '.' || c == ';' || c == ':' || c == '!' || c == '?')
        .trim()
        .to_string()
}

/// Deterministic web-search parser. Understands:
///   "search Iron Man on Google", "Google Iron Man", "look up Iron Man",
///   "find Iron Man videos", "play X on YouTube", "search YouTube for X",
///   and context follow-ups ("now search Avengers") via ctx.last_search_engine.
fn parse_search(text: &str, ctx: &SessionContext) -> Option<ParsedSearch> {
    let t = norm(text);
    if t.is_empty() {
        return None;
    }
    let explicit = extract_engine(text);
    let has_file_noun = FILE_WORDS.iter().any(|w| contains_word(&t, w));
    // Without an explicit platform, leave genuine file requests to the file tools.
    if has_file_noun && explicit.is_none() {
        return None;
    }

    let (engine_opt, body) = match &explicit {
        Some((engine, body)) => (Some(engine.clone()), body.clone()),
        None => (None, t.clone()),
    };

    // Find the action verb on a word boundary ("search" must not match inside
    // "research").
    let mut verb: Option<(&'static str, String)> = None;
    'verbs: for v in SEARCH_VERBS.iter().copied() {
        if v == "google" && engine_opt.is_some() {
            // "google" was already consumed as the platform.
            continue;
        }
        let mut search_from = 0usize;
        while let Some(rel) = body[search_from..].find(v) {
            let idx = search_from + rel;
            let prev_ok = idx == 0 || body.as_bytes()[idx - 1] == b' ';
            let after = idx + v.len();
            let next_ok = after >= body.len() || body.as_bytes().get(after).map(|c| *c == b' ').unwrap_or(true);
            if prev_ok && next_ok {
                let q = clean_query(&body[after..]);
                if !q.is_empty() {
                    verb = Some((v, q));
                    break 'verbs;
                }
            }
            search_from = idx + v.len();
            if search_from >= body.len() {
                break;
            }
        }
    }

    let (verb_name, query) = match verb {
        Some((v, q)) => (v, q),
        None => {
            // Leading engine verb ("Google Iron Man") leaves the whole body as
            // the query.
            if engine_opt.is_some() && !body.is_empty() {
                let q = clean_query(&body);
                if q.is_empty() {
                    return None;
                }
                ("google", q)
            } else {
                return None;
            }
        }
    };
    if query.is_empty() {
        return None;
    }

    // Choose the target engine: explicit platform wins; otherwise videos and
    // playback go to YouTube and everything else follows the last engine (or
    // Google by default - never a blanket YouTube default).
    let engine = match engine_opt {
        Some(e) => e,
        None => {
            let wants_video = verb_name == "play"
                || verb_name == "watch"
                || contains_word(&t, "video")
                || contains_word(&t, "videos")
                || contains_word(&t, "song")
                || contains_word(&t, "music")
                || contains_word(&t, "trailer");
            if wants_video {
                "youtube".to_string()
            } else {
                ctx.last_search_engine.clone().unwrap_or_else(|| "google".to_string())
            }
        }
    };
    Some(ParsedSearch {
        engine,
        query,
        action: if verb_name == "play" || verb_name == "watch" { "play" } else { "search" },
    })
}

fn browser_plan(text: &str, t: &str, w: &str, ctx: &SessionContext) -> Option<Vec<PlanItem>> {
    if ["close the browser", "close browser", "quit the browser", "quit browser", "exit the browser", "close the chrome window"]
        .iter().any(|k| t.contains(k))
    {
        return Some(vec![
            PlanItem::Step(NluStep { name: "close_browser".into(), arguments: serde_json::json!({}) }),
            PlanItem::Text("Browser closed, BOSS.".into()),
        ]);
    }
    if [" refresh ", " reload ", " reload the page "].iter().any(|k| w.contains(k)) {
        return Some(vec![
            PlanItem::Step(NluStep { name: "browser_key".into(), arguments: serde_json::json!({ "key": "F5" }) }),
            PlanItem::Text("Page refreshed, BOSS.".into()),
        ]);
    }
    if [" fullscreen ", " full screen ", " make it fullscreen "].iter().any(|k| w.contains(k)) {
        return Some(vec![
            PlanItem::Step(NluStep { name: "browser_key".into(), arguments: serde_json::json!({ "key": "F11" }) }),
            PlanItem::Text("Fullscreen toggled, BOSS.".into()),
        ]);
    }
    if ["what's on the screen", "what is on the screen", "what's on the page", "what is on the page",
        "what do you see", "snapshot the page", "read the page", "page snapshot", "browser snapshot",
        "what's open in the browser"].iter().any(|k| t.contains(k))
    {
        return Some(vec![
            PlanItem::Step(NluStep { name: "browser_snapshot".into(), arguments: serde_json::json!({}) }),
            PlanItem::Text("Here's what's on the page, BOSS.".into()),
        ]);
    }

    // --- Web searches (explicit platform, platform verb, or context) ---
    if let Some(s) = parse_search(text, ctx) {
        let url = engine_search_url(&s.engine, &s.query);
        let display = engine_display(&s.engine);
        let action_word = if s.action == "play" { "Playing" } else { "Searched" };
        return Some(vec![
            PlanItem::Step(NluStep {
                name: "browser_search".into(),
                arguments: serde_json::json!({ "query": s.query, "site": s.engine, "url": url }),
            }),
            PlanItem::Text(format!(
                "{} {} for '{}' - opened the results in your browser, BOSS.",
                action_word,
                display,
                s.query
            )),
        ]);
    }

    // --- explicit URL ---
    if let Some(caps) = Regex::new(r"(?i)https?://\S+").unwrap().captures(text) {
        let url = caps.get(0).unwrap().as_str().trim_end_matches(|c| c == '.' || c == ',' || c == ';' || c == '!' || c == '?');
        return Some(vec![
            PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
            PlanItem::Text(format!("Opening {}, BOSS.", url)),
        ]);
    }

    // --- "open <site>" via known sites ---
    if let Some(key) = site_keyword(text) {
        let url = SITE_URLS.iter().find(|(k, _)| *k == key).map(|(_, u)| *u).unwrap_or("");
        if ["open", "go to", "navigate", "visit", "browse", "launch", "start", "open up", "pull up"]
            .iter().any(|k| t.contains(k))
        {
            return Some(vec![
                PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
                PlanItem::Text(format!("Opened {}, BOSS.", key)),
            ]);
        }
    }

    // --- open <domain> / bare domain ---
    let has_open_verb = [" open ", " open up ", " go to ", " visit ", " navigate to ", " launch ", " start ", " browse to "]
        .iter().any(|k| w.contains(k))
        || t.starts_with("open ");
    if has_open_verb || (!text.contains(' ') && text.contains('.')) {
        let domain_re = Regex::new(r"(?i)\b([a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.(?:[a-z0-9-]+\.)*[a-z]{2,})\b").unwrap();
        if let Some(caps) = domain_re.captures(text) {
            let domain = caps.get(1).unwrap().as_str().trim_end_matches(|c: char| !c.is_alphanumeric());
            let tld = domain.rsplit('.').next().unwrap_or("").to_lowercase();
            let is_web_tld = WEB_TLDS.contains(&tld.as_str());
            let looks_like_file = tld.len() <= 4 && !is_web_tld;
            if is_web_tld || (has_open_verb && !looks_like_file) {
                let url = format!("https://{}", domain);
                return Some(vec![
                    PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
                    PlanItem::Text(format!("Opening {}, BOSS.", domain)),
                ]);
            }
        }
    }

    // --- bare engine/site word ("youtube", "google") opens the site ---
    let bare = norm(text);
    if !bare.contains(' ') {
        for (alias, engine, _) in SEARCH_ENGINES.iter().copied() {
            if alias == bare.as_str() && (alias.len() > 2 || contains_word(&bare, alias)) {
                let url = engine_home(engine);
                return Some(vec![
                    PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
                    PlanItem::Text(format!("Opened {}, BOSS.", engine_display(engine))),
                ]);
            }
        }
    }

    // --- nth-result follow-up on the current page ---
    let followup = ["second", "third", "fourth", "fifth", "2nd", "3rd", "4th", "5th",
        "next one", "next result", "next video", "first one", "first result", "top result", "another one"]
        .iter().any(|w2| Regex::new(&format!(r"(?i)\b{}\b", w2)).unwrap().is_match(t));
    if followup {
        let mut ordinal: u32 = 1;
        for (word, idx) in [("first", 0u32), ("1st", 0), ("second", 1), ("2nd", 1),
                            ("third", 2), ("3rd", 2), ("fourth", 3), ("4th", 3),
                            ("fifth", 4), ("5th", 4)] {
            if Regex::new(&format!(r"(?i)\b{}\b", word)).unwrap().is_match(t) {
                ordinal = idx;
                break;
            }
        }
        if ordinal == 1
            && ["next one", "next result", "next video", "another one"].iter().any(|k| t.contains(k))
        {
            ordinal = ctx.selected_result_index.unwrap_or(0) + 1;
        }
        return Some(vec![
            PlanItem::Text(format!(
                "The #{} result is waiting in your browser. I don't click inside pages without an automation bridge, so open it from there, BOSS.",
                ordinal + 1
            )),
        ]);
    }

    None
}


fn file_plan(text: &str, t: &str, w: &str, ctx: &SessionContext) -> Option<Vec<PlanItem>> {
    // ---- list directory
    if ["list files", "list the files", "list directory", "list contents", "show files",
        "show the files", "what's in", "what is in", "what's inside", "files in", "folders in",
        "directory listing", "contents of"].iter().any(|k| t.contains(k))
    {
        let directory = dir_from_text(text, ctx.current_directory.as_deref().unwrap_or("~"));
        return Some(vec![
            PlanItem::Step(NluStep { name: "list_directory".into(), arguments: serde_json::json!({ "path": directory }) }),
            PlanItem::Text(format!("Listing {}, BOSS.", directory)),
        ]);
    }

    // ---- find / search for files
    if (t.contains("find ") || t.contains("search for ") || t.contains("look for "))
        && ["file", "files", "document", "folder", "directory", "pdf", "matching", "named", "called"]
            .iter().any(|k| t.contains(k))
    {
        let query = t
            .replace("find ", "").replace("search for ", "").replace("look for ", "")
            .replace("files ", "").replace("file ", "").replace("documents ", "").replace("document ", "")
            .replace("matching ", "").replace("named ", "").replace("called ", "")
            .trim()
            .to_string();
        if !query.is_empty() {
            let location = ctx.current_directory.clone().unwrap_or_else(|| "~".into());
            return Some(vec![
                PlanItem::Step(NluStep { name: "find_files".into(), arguments: serde_json::json!({ "query": query, "location": location }) }),
                PlanItem::Text(format!("Searching for '{}', BOSS.", query)),
            ]);
        }
    }

    // ---- create a folder
    if has(text, &["create", "make", "new"]) && has(text, &["folder", "directory"]) {
        if let Some(name) = file_name_from(text) {
            if !["a", "the", "new", "folder", "directory"].contains(&name.to_lowercase().as_str()) {
                let parent = dir_from_text(text, "~/Documents");
                let path = format!("{}/{}", parent, name);
                return Some(vec![
                    PlanItem::Step(NluStep { name: "create_folder".into(), arguments: serde_json::json!({ "path": path }) }),
                    PlanItem::Text(format!("Creating folder {}, BOSS.", name)),
                ]);
            }
        }
    }

    // ---- create a file
    if has(text, &["create", "make", "new", "write"]) && has(text, &["file"]) {
        let name = Regex::new(r"(?i)(?:called|named)\s+([\w.\-]+(?:\.[A-Za-z0-9]+)?)")
            .unwrap().captures(text)
            .or_else(|| Regex::new(r"(?i)(?:file|document)\s+([\w.\-]+\.[A-Za-z0-9]{1,10})").unwrap().captures(text))
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().trim().to_string());
        if let Some(name) = name {
            let content = file_content(text);
            let parent = dir_from_text(text, "~/Documents");
            let path = format!("{}/{}", parent, name);
            return Some(vec![
                PlanItem::Step(NluStep { name: "create_file".into(), arguments: serde_json::json!({ "path": path, "content": content }) }),
                PlanItem::Text(format!("Creating {}, BOSS.", name)),
            ]);
        }
    }

    // ---- open folder
    let open_folder_phrase = t.contains("open the folder") || t.contains("open folder")
        || t.contains("show folder") || t.contains("open directory")
        || (t.contains("open") && t.contains("folder"));
    if open_folder_phrase {
        let name = file_name_from(text);
        let path = name.as_deref().map(|n| resolve_candidate(n, ctx))
            .or_else(|| ctx.current_directory.clone());
        if let Some(path) = path {
            return Some(vec![
                PlanItem::Step(NluStep { name: "open_folder".into(), arguments: serde_json::json!({ "path": path }) }),
                PlanItem::Text(format!("Opening {}, BOSS.", path)),
            ]);
        }
    }

    // ---- open file
    if (t.contains("open file") || t.contains("open the file") || t.contains("open up the file")
        || t.contains("read file") || t.contains("show me the file") || t.contains("open"))
        && !t.contains("application") && !t.contains("app ")
    {
        let name = Regex::new(r"(?i)(?:file\s+)?(?:called|named)?\s*([\w.\-/~]+\.\w{1,10})")
            .unwrap().captures(text).and_then(|c| c.get(1))
            .map(|m| m.as_str().trim().to_string());
        if let Some(name) = name {
            let path = resolve_candidate(&name, ctx);
            return Some(vec![
                PlanItem::Step(NluStep { name: "open_file".into(), arguments: serde_json::json!({ "path": path }) }),
                PlanItem::Text(format!("Opening {}, BOSS.", name)),
            ]);
        }
    }

    // ---- read a file
    if has(text, &["read", "contents of", "show contents"])
        && ["file", "document", "note", ".txt", ".md", "text"].iter().any(|k| t.contains(k))
    {
        let name = Regex::new(r"(?i)(?:file|document|note|text)\s+([\w.\-/~]+(?:\.\w+)?)")
            .unwrap().captures(t)
            .or_else(|| Regex::new(r"(?i)(?:called|named)?\s*([\w.\-/~]+\.\w{1,10})").unwrap().captures(text))
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().trim().to_string());
        if let Some(name) = name {
            let path = resolve_candidate(&name, ctx);
            let base = path.rsplit('/').next().unwrap_or(&path).to_string();
            return Some(vec![
                PlanItem::Step(NluStep { name: "read_file".into(), arguments: serde_json::json!({ "path": path }) }),
                PlanItem::Text(format!("Reading {}, BOSS.", base)),
            ]);
        }
    }

    // ---- delete a file
    if has(text, &["delete", "remove", "trash", "erase"])
        && ["file", "document", "note", "folder"].iter().any(|k| t.contains(k))
    {
        let name = Regex::new(r"(?i)(?:the\s+)?(?:file|document|folder|note)\s+(?:called|named)?\s*([\w.\-/~]+(?:\.\w+)?)")
            .unwrap().captures(text).and_then(|c| c.get(1))
            .map(|m| m.as_str().trim().to_string());
        if let Some(name) = name {
            let path = resolve_candidate(&name, ctx);
            return Some(vec![
                PlanItem::Step(NluStep { name: "delete_file".into(), arguments: serde_json::json!({ "path": path }) }),
                PlanItem::Text(format!("Deleting {}, BOSS.", name)),
            ]);
        }
    }

    // ---- move / rename / copy
    for (verb, tool) in [("rename", "move_file"), ("move", "move_file"), ("copy", "copy_file")] {
        let re = Regex::new(&format!(
            r"(?i){}\s+(?:the\s+)?(?:file|document|folder)?\s*(?:called|named)?\s*([\w./~-]+(?:\.[A-Za-z0-9]+)?)\s+(?:from\s+(.+?))?\s+to\s+([\w./~ -]+?)\s*$",
            verb
        )).unwrap();
        if let Some(caps) = re.captures(text.trim()) {
            let src_name = caps.get(1).unwrap().as_str().trim();
            let from_raw = caps.get(2).map(|m| m.as_str().trim()).unwrap_or_default();
            let dst_raw = caps.get(3).unwrap().as_str().trim();

            let dir_of = |token: &str| -> String {
                DIR_ALIASES.iter()
                    .filter(|(alias, _)| token.to_lowercase().contains(alias))
                    .max_by_key(|(alias, _)| alias.len())
                    .map(|(_, path)| expand_home(path))
                    .unwrap_or_default()
            };
            let src_folder = if from_raw.is_empty() { expand_home("~/Documents") } else { dir_of(from_raw) };
            let src_path = format!("{}/{}", src_folder, src_name);
            let dst_path = if dst_raw.starts_with('~') || dst_raw.starts_with('/') {
                expand_home(dst_raw)
            } else if !dir_of(dst_raw).is_empty() {
                format!("{}/{}", dir_of(dst_raw), std::path::Path::new(src_name).file_name().and_then(|f| f.to_str()).unwrap_or(src_name))
            } else if Regex::new(r"^[\w .-]+\.[A-Za-z0-9]{1,10}$").unwrap().is_match(dst_raw) {
                format!("{}/{}", std::path::Path::new(&src_path).parent().map(|p| p.display().to_string()).unwrap_or_default(), dst_raw)
            } else {
                format!("{}/{}", std::path::Path::new(&src_path).parent().map(|p| p.display().to_string()).unwrap_or_default(), dst_raw)
            };
            let action = if tool == "move_file" { "Moving" } else { "Copying" };
            return Some(vec![
                PlanItem::Step(NluStep { name: tool.into(), arguments: serde_json::json!({ "source": src_path, "destination": dst_path }) }),
                PlanItem::Text(format!("{} {} to {}, BOSS.", action, src_name, std::path::Path::new(&dst_path).file_name().and_then(|f| f.to_str()).unwrap_or(&dst_path))),
            ]);
        }
    }

    None
}

fn messaging_plan(text: &str, t: &str) -> Option<Vec<PlanItem>> {
    let app = if t.contains("whatsapp") {
        Some("whatsapp")
    } else if t.contains("telegram") || t.contains("tg ") {
        Some("telegram")
    } else if t.contains("signal") {
        Some("signal")
    } else {
        None
    }?;
    let app_title = app.to_string();
    if ["open ", "launch ", "go to ", "start "].iter().any(|k| t.contains(k))
        && !["send", "message", "text", "tell", "ping", "notify"].iter().any(|k| t.contains(k))
    {
        return Some(vec![
            PlanItem::Step(NluStep { name: "open_chat_app".into(), arguments: serde_json::json!({ "app": app }) }),
            PlanItem::Text(format!("Opened {}, BOSS.", app_title)),
        ]);
    }
    let send_verbs = ["send", "message", "text", "tell", "ping", "notify", "write to", "msg"];
    if !send_verbs.iter().any(|k| t.contains(k)) && !t.starts_with(&format!("{} ", app)) {
        return None;
    }
    let mut recipient_part = t.to_string();
    let mut content = String::new();
    let re_q = Regex::new(r#"["'](.+?)["']"#).unwrap();
    let quoted = re_q.captures(text).map(|c| c.get(1).unwrap().as_str().trim().to_string());
    for marker in ["saying that ", "saying ", "that says ", "the message ", "with the message ",
                   "the following ", "telling him ", "telling her ", "text: ", " that ", ": "] {
        if let Some(idx) = recipient_part.find(marker) {
            let content_raw = text[idx + marker.len()..].trim().trim_matches(|c| c == ' ' || c == '\'' || c == '"').to_string();
            recipient_part = recipient_part[..idx].to_string();
            content = content_raw;
            break;
        }
    }
    if content.is_empty() {
        if let Some(q) = quoted {
            content = q;
        }
    }
    if content.starts_with("that ") {
        content = content[5..].to_string();
    }
    if content.is_empty() {
        return Some(vec![
            PlanItem::Step(NluStep { name: "open_chat_app".into(), arguments: serde_json::json!({ "app": app }) }),
            PlanItem::Text(format!("Tell me who to message on {} and what to say, BOSS.", app_title)),
        ]);
    }
    let mut recipient = if let Some(pos) = recipient_part.rfind(" to ") {
        recipient_part[pos + 4..].to_string()
    } else {
        recipient_part
            .replace(app, "")
            .replace("send", "").replace("message", "").replace("text", "")
            .replace("tell", "").replace("ping", "").replace("notify", "")
            .replace("write to", "").replace("msg", "").replace("please", "")
            .trim()
            .to_string()
    };
    for prefix in ["a ", "an ", "the ", "my ", "to ", "for "] {
        recipient = recipient.trim_start_matches(prefix).to_string();
    }
    let re_tail = Regex::new(r"\s+(on|via|using)\s+(whatsapp|telegram|signal).*$").unwrap();
    recipient = re_tail.replace(&recipient, "").to_string();
    recipient = recipient.trim().trim_matches(|c| c == ' ' || c == ',' || c == ':' || c == '\'' || c == '"' || c == '.' || c == '-').to_string();
    if recipient.is_empty() {
        return Some(vec![
            PlanItem::Step(NluStep { name: "open_chat_app".into(), arguments: serde_json::json!({ "app": app }) }),
            PlanItem::Text(format!("Who should I message on {}?", app_title)),
        ]);
    }
    Some(vec![
        PlanItem::Step(NluStep {
            name: "send_message".into(),
            arguments: serde_json::json!({ "app": app, "recipient": recipient, "message": content }),
        }),
        PlanItem::Text(format!("Sending to {} on {}, BOSS.", recipient, app_title)),
    ])
}

fn terminal_plan(text: &str, t: &str) -> Option<Vec<PlanItem>> {
    let triggers = ["run the command", "run command", "execute the command", "execute command",
        "run the terminal command"];
    let starts = t.starts_with("run ") || t.starts_with("execute ") || t.starts_with("terminal:");
    if !triggers.iter().any(|k| t.contains(k)) && !starts {
        return None;
    }
    let mut raw = Regex::new(r"(?i)^(?:please\s+)?(?:run the command|run command|execute the command|execute command|run the terminal command|run|execute|terminal:)\s*")
        .unwrap().replace(text, "").to_string();
    raw = Regex::new(r"\s*(please|thanks|thank you)$").unwrap().replace(&raw, "").to_string();
    raw = Regex::new(r"\s+in the terminal$").unwrap().replace(&raw, "").to_string();
    raw = Regex::new(r"\s+using the terminal$").unwrap().replace(&raw, "").to_string();
    let raw = raw.trim().trim_matches(|c| c == '\'' || c == '"').to_string();
    if raw.is_empty() || ["it", "that", "a command", "command", "terminal"].contains(&raw.to_lowercase().as_str()) {
        return None;
    }
    if is_app_or_site_ref(&raw) {
        return None; // "run spotify/firefox" is an app launch
    }
    Some(vec![
        PlanItem::Step(NluStep { name: "execute_command".into(), arguments: serde_json::json!({ "command": raw }) }),
        PlanItem::Text(format!("Running '{}', BOSS.", raw)),
    ])
}

fn application_plan(text: &str, t: &str, w: &str) -> Option<Vec<PlanItem>> {
    if ["what apps are running", "what applications are running", "which apps are running",
        "which apps are open", "list running apps", "list running applications",
        "show running apps", "running apps", "running applications", "apps running",
        "open applications", "what programs are running", "programs running"].iter().any(|k| t.contains(k))
    {
        return Some(vec![
            PlanItem::Step(NluStep { name: "list_running_applications".into(), arguments: serde_json::json!({}) }),
            PlanItem::Text("Here are the running applications, BOSS.".into()),
        ]);
    }
    // Open the user's default browser (not a hard-coded one).
    if ["open browser", "open the browser", "open a browser", "launch browser", "launch the browser",
        "start browser", "start the browser", "open up the browser", "open web browser",
        "open my browser", "open default browser", "start a browser", "open the web browser",
        "open a web browser", "launch the web browser"].iter().any(|k| t.contains(k))
    {
        return Some(vec![
            PlanItem::Step(NluStep { name: "open_browser".into(), arguments: serde_json::json!({}) }),
            PlanItem::Text("Opening your default browser, BOSS.".into()),
        ]);
    }
    if [" switch to ", " focus on ", " focus ", " bring up ", " switch over to ", " go to the "]
        .iter().any(|k| w.contains(k))
    {
        if let Some(app) = app_alias(text) {
            return Some(vec![
                PlanItem::Step(NluStep { name: "switch_to_application".into(), arguments: serde_json::json!({ "application": app }) }),
                PlanItem::Text(format!("Switched to {}, BOSS.", app)),
            ]);
        }
        return None;
    }
    if [" close ", " quit ", " exit ", " kill "].iter().any(|k| w.contains(k))
        && (t.contains("app") || t.contains("application") || t.contains("program") || app_alias(text).is_some())
    {
        if let Some(app) = app_alias(text) {
            return Some(vec![
                PlanItem::Step(NluStep { name: "close_application".into(), arguments: serde_json::json!({ "application": app }) }),
                PlanItem::Text(format!("Closed {}, BOSS.", app)),
            ]);
        }
        return None;
    }
    let open_words = [" open ", " launch ", " start ", " run ", " open up ", " pull up "];
    if open_words.iter().any(|k| w.contains(k)) || t.starts_with("open ") {
        let rest = Regex::new(r"(?i)^(?:please\s+)?(?:open up|open|launch|start|run|pull up)\s+(?:the\s+|a\s+)?")
            .unwrap().replace(t, "").to_string();
        let rest = rest.trim().to_string();
        if let Some(app) = app_alias(text) {
            return Some(vec![
                PlanItem::Step(NluStep { name: "open_application".into(), arguments: serde_json::json!({ "application": app }) }),
                PlanItem::Text(format!("Opening {}, BOSS.", app)),
            ]);
        }
        if let Some((_, url)) = KNOWN_WEBSITES.iter().find(|(k, _)| *k == rest) {
            return Some(vec![
                PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
                PlanItem::Text(format!("Opened {}, BOSS.", rest)),
            ]);
        }
        if let Some((key, url)) = SITE_URLS.iter().find(|(k, _)| *k == rest) {
            return Some(vec![
                PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
                PlanItem::Text(format!("Opened {}, BOSS.", key)),
            ]);
        }
        if Regex::new(r"[\w-]+\.[a-z]{2,}").unwrap().is_match(&rest) {
            let url = if rest.starts_with("http") { rest.clone() } else { format!("https://{}", rest) };
            return Some(vec![
                PlanItem::Step(NluStep { name: "open_url".into(), arguments: serde_json::json!({ "url": url }) }),
                PlanItem::Text(format!("Opened {}, BOSS.", rest)),
            ]);
        }
        return Some(vec![
            PlanItem::Step(NluStep { name: "open_application".into(), arguments: serde_json::json!({ "application": rest }) }),
            PlanItem::Text(format!("Opening {}, BOSS.", rest)),
        ]);
    }
    None
}
/// Structured readout of what PLUTO understood, for the UI brain panel:
/// intent / target / platform / query / url / action.
pub fn command_meta(text: &str, ctx: &SessionContext) -> serde_json::Value {
    use serde_json::json;
    let items = plan(text, ctx);
    for item in &items {
        let PlanItem::Step(step) = item else { continue };
        let name = step.name.as_str();
        let a = &step.arguments;
        let get = |k: &str| a.get(k).and_then(|v| v.as_str()).unwrap_or("").to_string();
        let mut target = String::new();
        let mut platform = String::new();
        let mut query = String::new();
        let mut url = String::new();
        // `intent` and `action` are assigned in every match arm below.
        let mut intent: String;
        let mut action: String;
        match name {
            "browser_search" => {
                query = get("query");
                url = get("url");
                platform = {
                    let site = get("site");
                    if site.is_empty() { site_from_url(&url) } else { site }
                };
                target = query.clone();
                intent = "web_search".to_string();
                action = "search".to_string();
            }
            "open_url" => {
                url = get("url");
                target = url.clone();
                platform = site_from_url(&url);
                intent = "open_website".to_string();
                action = "open".to_string();
            }
            "open_browser" => {
                target = "default browser".to_string();
                intent = "open_browser".to_string();
                action = "open".to_string();
            }
            "open_application" | "close_application" | "switch_to_application" => {
                target = get("application");
                intent = name.replace('_', " ");
                action = "run".to_string();
            }
            "take_screenshot" => {
                intent = "take_screenshot".to_string();
                action = "capture".to_string();
                platform = get("area");
            }
            "set_volume" | "get_volume" => {
                intent = "volume".to_string();
                target = get("level");
                action = if name == "set_volume" { "set" } else { "read" }.to_string();
            }
            "copy_to_clipboard" | "get_clipboard" => {
                intent = "clipboard".to_string();
                target = get("text");
                action = if name == "copy_to_clipboard" { "copy" } else { "read" }.to_string();
            }
            "get_processes" | "kill_process" => {
                intent = "process".to_string();
                target = if name == "get_processes" { get("name") } else { get("process") };
                action = if name == "kill_process" { "kill" } else { "list" }.to_string();
            }
            "execute_command" => {
                intent = "run_command".to_string();
                target = get("command");
                action = "execute".to_string();
            }
            "create_folder" | "create_file" | "delete_file" | "read_file" | "list_directory"
            | "open_file" | "open_folder" | "find_files" | "move_file" | "copy_file" => {
                intent = name.replace('_', " ");
                target = if !get("path").is_empty() { get("path") } else { get("source") };
                query = get("query");
                action = "run".to_string();
            }
            _ => {
                intent = name.replace('_', " ");
                action = "run".to_string();
            }
        }
        let mut data = json!({ "intent": intent });
        if !target.is_empty() { data["target"] = json!(target); }
        if !platform.is_empty() { data["platform"] = json!(platform); }
        if !query.is_empty() { data["query"] = json!(query); }
        if !url.is_empty() { data["url"] = json!(url); }
        if !action.is_empty() { data["action"] = json!(action); }
        return data;
    }
    json!({ "intent": "conversation", "action": "reply" })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn steps(plan: &[PlanItem]) -> Vec<String> {
        plan.iter()
            .filter_map(|p| match p {
                PlanItem::Step(s) => Some(s.name.clone()),
                _ => None,
            })
            .collect()
    }

    fn first_step(plan: &[PlanItem]) -> Option<NluStep> {
        plan.iter().find_map(|p| match p {
            PlanItem::Step(s) => Some(s.clone()),
            _ => None,
        })
    }

    fn search_arg(plan: &[PlanItem], key: &str) -> String {
        first_step(plan)
            .and_then(|s| s.arguments.get(key).and_then(|v| v.as_str()).map(|v| v.to_string()))
            .unwrap_or_default()
    }

    // --- required natural commands -----------------------------------------

    #[test]
    fn search_google_explicit() {
        for cmd in [
            "Search Iron Man on Google",
            "Google Iron Man",
            "find Iron Man on Google",
            "look up Iron Man",
            "search the web for Iron Man",
            "please search for iron man on google",
        ] {
            let p = plan(cmd, &SessionContext::default());
            assert_eq!(steps(&p), vec!["browser_search"], "cmd: {cmd}");
            assert_eq!(search_arg(&p, "site"), "google", "cmd: {cmd}");
            let url = search_arg(&p, "url");
            assert!(url.starts_with("https://www.google.com/search?q="), "cmd: {cmd} url: {url}");
            assert!(url.to_lowercase().contains("iron%20man"), "cmd: {cmd} url: {url}");
        }
    }

    #[test]
    fn search_youtube_explicit() {
        for cmd in [
            "Search Iron Man on YouTube",
            "find Iron Man videos",
            "play Iron Man on YouTube",
            "search youtube for iron man trailer",
            "Find Avengers trailer on YouTube",
        ] {
            let p = plan(cmd, &SessionContext::default());
            let s = steps(&p);
            assert_eq!(s, vec!["browser_search"], "cmd: {cmd}");
            assert_eq!(search_arg(&p, "site"), "youtube", "cmd: {cmd}");
            let url = search_arg(&p, "url");
            assert!(url.starts_with("https://www.youtube.com/results?search_query="), "cmd: {cmd} url: {url}");
        }
    }

    #[test]
    fn search_default_is_google_not_youtube() {
        let p = plan("Search Iron Man", &SessionContext::default());
        assert_eq!(steps(&p), vec!["browser_search"]);
        assert_eq!(search_arg(&p, "site"), "google");
        assert_eq!(search_arg(&p, "query"), "iron man");
        assert!(search_arg(&p, "url").starts_with("https://www.google.com/search?q="));
    }

    #[test]
    fn followup_reuses_last_engine() {
        // After a Google search, "search Avengers" stays on Google.
        let mut ctx = SessionContext::default();
        ctx.last_search_engine = Some("google".to_string());
        let p = plan("Now search Avengers", &ctx);
        assert_eq!(steps(&p), vec!["browser_search"]);
        assert_eq!(search_arg(&p, "site"), "google");
        assert_eq!(search_arg(&p, "query"), "avengers");

        // After YouTube, the same follow-up goes to YouTube.
        let mut ctx = SessionContext::default();
        ctx.last_search_engine = Some("youtube".to_string());
        let p = plan("now search iron man", &ctx);
        assert_eq!(steps(&p), vec!["browser_search"]);
        assert_eq!(search_arg(&p, "site"), "youtube");
    }

    #[test]
    fn play_on_youtube_opens_search_results_not_a_click() {
        let p = plan("Play Iron Man trailer on YouTube", &SessionContext::default());
        let s = steps(&p);
        assert_eq!(s, vec!["browser_search"], "must generate a results URL, not attempt DOM clicks");
        assert!(search_arg(&p, "url").starts_with("https://www.youtube.com/results?search_query="));
    }

    #[test]
    fn search_bing() {
        let p = plan("Search Linux on Bing", &SessionContext::default());
        assert_eq!(steps(&p), vec!["browser_search"]);
        assert_eq!(search_arg(&p, "site"), "bing");
        assert!(search_arg(&p, "url").starts_with("https://www.bing.com/search?q="));
    }

    #[test]
    fn open_browser_command() {
        for cmd in ["open browser", "launch the browser", "open my browser", "start a browser"] {
            let p = plan(cmd, &SessionContext::default());
            assert_eq!(steps(&p), vec!["open_browser"], "cmd: {cmd}");
        }
    }

    #[test]
    fn open_specific_browsers() {
        for (cmd, app) in [("launch Chrome", "google-chrome"), ("open Firefox", "firefox")] {
            let p = plan(cmd, &SessionContext::default());
            assert_eq!(steps(&p), vec!["open_application"], "cmd: {cmd}");
            let step = first_step(&p).expect("step");
            assert_eq!(step.arguments["application"], app, "cmd: {cmd}");
        }
    }

    #[test]
    fn open_sites_and_domains() {
        for (cmd, expected) in [
            ("open GitHub", "https://github.com"),
            ("Open Gmail", "https://mail.google.com"),
            ("open Google", "https://www.google.com"),
            ("Open YouTube", "https://www.youtube.com"),
            ("open example.com", "https://example.com"),
            ("open example.com in the browser", "https://example.com"),
        ] {
            let p = plan(cmd, &SessionContext::default());
            assert_eq!(steps(&p), vec!["open_url"], "cmd: {cmd}");
            assert_eq!(search_arg(&p, "url"), expected, "cmd: {cmd}");
        }
    }

    #[test]
    fn bare_domain_opens() {
        let p = plan("example.com", &SessionContext::default());
        assert_eq!(steps(&p), vec!["open_url"]);
        assert_eq!(search_arg(&p, "url"), "https://example.com");
    }

    #[test]
    fn youtube_bare_word_opens_site() {
        let p = plan("YouTube", &SessionContext::default());
        assert_eq!(steps(&p), vec!["open_url"]);
        assert_eq!(search_arg(&p, "url"), "https://www.youtube.com");
    }

    // --- preserved legacy behavior -----------------------------------------

    #[test]
    fn routes_screenshot() {
        let p = plan("take a screenshot", &SessionContext::default());
        assert_eq!(steps(&p), vec!["take_screenshot"]);
    }

    #[test]
    fn routes_clipboard() {
        let p = plan("copy 'hello boss' to the clipboard", &SessionContext::default());
        assert_eq!(steps(&p), vec!["copy_to_clipboard"]);
    }

    #[test]
    fn routes_create_folder() {
        let p = plan("Create a folder called PLUTO inside my Projects directory", &SessionContext::default());
        assert_eq!(steps(&p), vec!["create_folder"]);
    }

    #[test]
    fn routes_open_youtube_and_play() {
        // Single deterministic action: search the query on YouTube directly.
        let p = plan("Open YouTube and play a great song", &SessionContext::default());
        let s = steps(&p);
        assert_eq!(s, vec!["browser_search"]);
        assert_eq!(search_arg(&p, "site"), "youtube");
        assert_eq!(search_arg(&p, "query"), "great song");
    }

    #[test]
    fn routes_open_app() {
        let p = plan("open vscode", &SessionContext::default());
        assert_eq!(steps(&p), vec!["open_application"]);
        if let PlanItem::Step(s) = &p[0] {
            assert_eq!(s.arguments["application"], "code");
        }
    }

    #[test]
    fn routes_system_status() {
        let p = plan("check system status and optimize memory", &SessionContext::default());
        assert_eq!(steps(&p), vec!["get_processes"]);
    }

    #[test]
    fn routes_terminal_command() {
        let p = plan("run the command ls -la", &SessionContext::default());
        assert_eq!(steps(&p), vec!["execute_command"]);
    }

    #[test]
    fn routes_open_url_domain() {
        let p = plan("open example.com", &SessionContext::default());
        if let PlanItem::Step(s) = &p[0] {
            assert_eq!(s.name, "open_url");
            assert_eq!(s.arguments["url"], "https://example.com");
        }
    }

    #[test]
    fn command_meta_readout() {
        let m = command_meta("Search Iron Man on Google", &SessionContext::default());
        assert_eq!(m["intent"], "web_search");
        assert_eq!(m["platform"], "google");
        assert_eq!(m["query"], "iron man");
        assert_eq!(m["action"], "search");
        assert!(m["url"].as_str().unwrap_or("").starts_with("https://www.google.com/search?q="));
    }

    #[test]
    fn capabilities_on_unknown() {
        let p = plan("do a totally random thing", &SessionContext::default());
        assert!(p.iter().all(|i| matches!(i, PlanItem::Text(_))));
    }
}
