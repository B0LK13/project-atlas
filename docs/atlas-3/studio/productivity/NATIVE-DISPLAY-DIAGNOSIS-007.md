# Native Display Diagnosis 007

## Session

- Session type: native Wayland (`loginctl ... Type=wayland`, `XDG_SESSION_TYPE=wayland`)
- Wayland socket: `/run/user/1000/wayland-0` (present and accessible to the user)
- Runtime directory: `/run/user/1000`
- Session bus: `/run/user/1000/bus` (DBus portal and AT-SPI bus reachable)
- X11 compatibility: `DISPLAY=:0` is present, but X11 is not the authoritative desktop surface

## Controlled comparison

Both executables were launched as the same user with:

```text
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
```

Current candidate executable (`8e6eb2fd` lineage) emitted Wayland protocol traffic including `xdg_toplevel`, `xdg_surface.set_window_geometry`, EGL buffer creation, `wl_surface.attach`, and repeated `wl_surface.commit` operations while remaining alive through the controlled timeout. The preserved comparison executable SHA-256 is `801623e822b8060806b1353db47233f90f97f7b2564f40fa83409e3b8060d770`; it emitted the same Wayland surface and EGL traffic under the same conditions.

Current executable SHA-256: `0438b41843ea211e10b920c1a03908be6c532b1de9354cf8fcf6ae03cdb8d82e`.

## Classification

The process is alive and rendering a native Wayland surface. `xprop`, `xwininfo`, and `_NET_CLIENT_LIST` cannot observe that surface, so their empty Atlas result does not indicate missing window creation or an application startup failure. No Studio repair is indicated by this evidence.

## Resume action

Native interaction acceptance requires a Wayland-aware capture/accessibility path (for example GNOME Shell/portal capture plus AT-SPI inspection) or an X11 desktop session explicitly selected by the operator. Keep the existing session access controls; do not disable WebKit sandboxing or CSP. Browser evidence remains separate from native acceptance.

Documentation synchronization remains independently blocked and is not causal to this display finding.
