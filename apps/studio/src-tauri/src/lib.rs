//! Atlas Studio native lifecycle shell.
//!
//! Bounded authority boundary: no commands are registered, no shell/filesystem
//! plugins are installed, and closing this UI does not terminate Atlas work.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running Atlas Studio");
}
