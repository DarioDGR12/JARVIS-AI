use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, State};

/// 0 = off, 1 = region hit-test, 2 = force click-through.
struct HitMode(Arc<AtomicU8>);
struct VisorOn(Arc<AtomicBool>);

#[tauri::command]
fn brain_url() -> String {
    std::env::var("JARVIS_BRAIN_URL").unwrap_or_else(|_| "http://127.0.0.1:8765".into())
}

fn apply_background(win: &tauri::WebviewWindow, visor: bool) {
    let color = if visor {
        Some(tauri::window::Color(0, 0, 0, 0))
    } else {
        Some(tauri::window::Color(7, 9, 13, 255))
    };
    let _ = win.set_background_color(color);
}

#[tauri::command]
fn set_visor(
    app: tauri::AppHandle,
    mode: State<HitMode>,
    visor: State<VisorOn>,
    enabled: bool,
) -> Result<(), String> {
    let Some(win) = app.get_webview_window("main") else {
        return Ok(());
    };
    win.set_always_on_top(enabled)
        .map_err(|err| err.to_string())?;
    apply_background(&win, enabled);
    visor.0.store(enabled, Ordering::Relaxed);
    if !enabled {
        let _ = win.set_ignore_cursor_events(false);
        mode.0.store(0, Ordering::Relaxed);
    } else {
        mode.0.store(1, Ordering::Relaxed);
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
fn set_click_through(
    app: tauri::AppHandle,
    mode: State<HitMode>,
    visor: State<VisorOn>,
    enabled: bool,
) -> Result<(), String> {
    let Some(win) = app.get_webview_window("main") else {
        return Ok(());
    };
    if enabled {
        mode.0.store(2, Ordering::Relaxed);
        win.set_ignore_cursor_events(true)
            .map_err(|err| err.to_string())?;
    } else if visor.0.load(Ordering::Relaxed) {
        mode.0.store(1, Ordering::Relaxed);
    } else {
        mode.0.store(0, Ordering::Relaxed);
        let _ = win.set_ignore_cursor_events(false);
    }
    Ok(())
}

#[tauri::command]
fn set_overlay(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    let Some(win) = app.get_webview_window("overlay") else {
        return Ok(());
    };
    apply_background(&win, true);
    if enabled {
        win.set_always_on_top(true)
            .map_err(|err| err.to_string())?;
        let _ = win.set_ignore_cursor_events(true);
        win.show().map_err(|err| err.to_string())?;
    } else {
        let _ = win.set_ignore_cursor_events(false);
        win.hide().map_err(|err| err.to_string())?;
    }
    Ok(())
}

fn spawn_hit_loop(app: tauri::AppHandle, flag: Arc<AtomicU8>) {
    thread::spawn(move || loop {
        thread::sleep(Duration::from_millis(40));
        let mode = flag.load(Ordering::Relaxed);
        let Some(win) = app.get_webview_window("main") else {
            continue;
        };
        if mode == 0 {
            continue;
        }
        if mode == 2 {
            let _ = win.set_ignore_cursor_events(true);
            continue;
        }
        let (Ok(cursor), Ok(origin), Ok(size)) =
            (win.cursor_position(), win.outer_position(), win.inner_size())
        else {
            continue;
        };
        let x = cursor.x - f64::from(origin.x);
        let y = cursor.y - f64::from(origin.y);
        let w = f64::from(size.width);
        let h = f64::from(size.height);
        let inside = x >= 0.0 && y >= 0.0 && x <= w && y <= h;
        let chrome = inside && (y < 92.0 || x > w - 248.0);
        let _ = win.set_ignore_cursor_events(!chrome);
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            brain_url,
            set_visor,
            set_click_through,
            set_overlay
        ])
        .setup(|app| {
            let flag = Arc::new(AtomicU8::new(0));
            app.manage(HitMode(flag.clone()));
            app.manage(VisorOn(Arc::new(AtomicBool::new(false))));
            spawn_hit_loop(app.handle().clone(), flag);
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
