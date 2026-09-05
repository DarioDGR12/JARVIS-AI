use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;

#[tauri::command]
fn brain_url() -> String {
    std::env::var("JARVIS_BRAIN_URL").unwrap_or_else(|_| "http://127.0.0.1:8765".into())
}

#[tauri::command]
fn set_visor(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    let Some(win) = app.get_webview_window("main") else {
        return Ok(());
    };
    win.set_always_on_top(enabled)
        .map_err(|err| err.to_string())?;
    if !enabled {
        let _ = win.set_ignore_cursor_events(false);
    }
    let size = if enabled {
        tauri::LogicalSize::new(440.0, 560.0)
    } else {
        tauri::LogicalSize::new(1040.0, 700.0)
    };
    let _ = win.set_size(tauri::Size::Logical(size));
    Ok(())
}

#[tauri::command]
fn set_click_through(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    let Some(win) = app.get_webview_window("main") else {
        return Ok(());
    };
    win.set_ignore_cursor_events(enabled)
        .map_err(|err| err.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![brain_url, set_visor, set_click_through])
        .setup(|app| {
            let show = MenuItem::with_id(app, "show", "Mostrar", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Salir", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            let mut tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("JARVIS");
            if let Some(icon) = app.default_window_icon().cloned() {
                tray = tray.icon(icon);
            }
            let _tray = tray
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "quit" => app.exit(0),
                    "show" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.set_ignore_cursor_events(false);
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running JARVIS");
}
