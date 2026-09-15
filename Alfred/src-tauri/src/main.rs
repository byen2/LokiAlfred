// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    sync::Mutex,
    thread,
    time::Duration,
};

use tauri::{
    Manager,
    tray::TrayIconBuilder,
    menu::{Menu, MenuItem},
    WindowEvent,
};

use tauri_plugin_shell::ShellExt;

struct BackendProcess(
    Mutex<Option<tauri_plugin_shell::process::CommandChild>>
);

//Adjusted to give pysinstaller time to initialize
fn wait_for_backend() -> bool {
    thread::sleep(Duration::from_millis(500));

    for attempt in 1..=60 {
        println!("Checking backend... attempt {}/60", attempt);

        match reqwest::blocking::get("http://127.0.0.1:8001/") {
            Ok(response) if response.status().is_success() => {
                println!("Backend is ready.");
                return true;
            }

            Ok(response) => {
                eprintln!(
                    "Backend responded with HTTP {}. Retrying...",
                    response.status()
                );
            }

            Err(error) => {
                eprintln!(
                    "Backend not ready yet: {}",
                    error
                );
            }
        }

        thread::sleep(Duration::from_millis(500));
    }

    eprintln!("Backend failed to become ready after 30 seconds.");
    false
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess(Mutex::new(None)))

        .setup(|app| {

            // -------------------------
            // START UVICORN
            // -------------------------
            let sidecar = app
                .shell()
                .sidecar("backend")?;
            
            let (_rx, child) = sidecar.spawn()?;
            
            let state = app.state::<BackendProcess>();
            *state.0.lock().unwrap() = Some(child);

            println!("Backend sidecar started.");

            // -------------------------
            // TRAY MENU
            // -------------------------
            let open = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &quit])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(move |app, event| {
                    match event.id.as_ref() {

                        "open" => {
                            let window = app.get_webview_window("main").unwrap();
                            let _ = window.show();
                            let _ = window.set_focus();
                        }

                        "quit" => {
                            if let Some(state) = app.try_state::<BackendProcess>() {
                                if let Some(child) = state.0.lock().unwrap().take() {
                                    let _ = child.kill();
                                }
                            }
                            app.exit(0);
                        }

                        _ => {}
                    }
                })
                .build(app)?;

            // -------------------------
            // WAIT + NAVIGATE
            // -------------------------
            if wait_for_backend() {
                println!("Backend confirmed healthy. Loading Alfred.");
            
                let window = app.get_webview_window("main").unwrap();
            
                let _ = window.eval(
                    "window.location.replace('http://127.0.0.1:8001');"
                );
            
                let _ = window.show();
                let _ = window.set_focus();
            } else {
                eprintln!("Alfred backend failed to start.");
            }

            Ok(())
        })

        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })

        .run(tauri::generate_context!())
        .expect("error running tauri app");
}