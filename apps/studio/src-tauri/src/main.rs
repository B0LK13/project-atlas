fn main() {
    // D-006: GTK 4.1 contexts default to no WebProcess sandbox. Enable it
    // before Tauri starts any threads or creates a WebKit context.
    #[cfg(target_os = "linux")]
    {
        if std::env::var_os("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS").is_some() {
            eprintln!("Atlas Studio requires the WebKit sandbox; remove WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS.");
            std::process::exit(1);
        }
        std::env::set_var("WEBKIT_FORCE_SANDBOX", "1");
    }
    atlas_studio_lib::run();
}
