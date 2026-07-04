// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    process::{Command, Stdio},
    sync::Mutex,
    thread,
    time::Duration,
    net::TcpStream,
};

use tauri::{
    Manager,
    tray::TrayIconBuilder,
    menu::{Menu, MenuItem},
    WindowEvent,
};

struct BackendProcess(Mutex<Option<std::process::Child>>);

fn wait_for_backend() {
    for _ in 0..50 {
        if TcpStream::connect("127.0.0.1:8001").is_ok() {
            return;
        }
        thread::sleep(Duration::from_millis(100));
    }
}

fn main() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))

        .setup(|app| {

            // -------------------------
            // START UVICORN
            // -------------------------
            let child = Command::new("/Users/benoityen/.pyenv/shims/python3")
                .args([
                    "-m",
                    "uvicorn",
                    "app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8001",
                ])
                .current_dir("/Users/benoityen/Desktop/recoll_demo")
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .spawn()
                .expect("failed to start backend");

            let state = app.state::<BackendProcess>();
            *state.0.lock().unwrap() = Some(child);

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
                                if let Some(mut child) = state.0.lock().unwrap().take() {
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
            wait_for_backend();

            let window = app.get_webview_window("main").unwrap();

            let _ = window.eval(
                "window.location.replace('http://127.0.0.1:8001');"
            );

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