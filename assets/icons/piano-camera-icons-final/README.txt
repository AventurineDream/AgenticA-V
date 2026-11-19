Piano-camera app icon (final, v2.2): alternate colour options
==================================================

Default (unchanged): orange body on a teal plate. It is in default/.

Variants (each folder has AppIcon-1024.png, AppIcon.svg, AppIcon-32.svg, AppIcon-16.svg,
AppIcon.iconset/ with all 10 sizes, and AppIcon.icns):
  red-orange     red-orange body on a deep teal plate
  yellow-orange  marigold body on an indigo plate
  yellow-green   lime body on a plum plate
  blue-green     teal body on a rust/brick plate
  blue-violet    violet body on a warm gold plate
  red-violet     magenta body on a forest-green plate
  mono-dark      light grey body on a near-black plate (pure greyscale)
  mono-light     dark grey body on a light grey plate (pure greyscale)
16 px and 32 px use simplified artwork, recoloured to match.
The menu bar icon (menubar/MenuBarIconTemplate*) is a template image. macOS tints it,
so there are no colour variants of it.

How alternate icons work on macOS (please check against Apple's current docs)
--------------------------------------------------------------------------------
- macOS has no equivalent of iOS's UIApplication.setAlternateIconName.
  The icon Finder shows comes from the app bundle (CFBundleIconFile / the AppIcon
  asset in Assets.xcassets) and is fixed at build time.
- At runtime, an app can change its Dock icon while it is running by setting
  NSApplication.shared.applicationIconImage = NSImage(...), or by drawing a custom
  view into NSApp.dockTile.contentView and then calling NSApp.dockTile.display().
  Usually the choice does not persist after the app quits; the app has to set it
  again on each launch, typically from a saved user preference.
- A Dock Tile plug-in (NSDockTilePlugIn, NSDockTilePlugInClass in Info.plist) can
  change the Dock icon even when the app is not running. It is more work to set up.
- NSWorkspace.shared.setIcon(_:forFile:options:) can set a custom Finder icon on the
  .app bundle itself. This changes a file attribute on the app, which can be fragile:
  app updates may reset it, and it may conflict with code signing or with apps
  installed from the App Store. Test this before relying on it.
- Common practice is to ship the alternate icons as image assets in the app (for
  example the 1024 PNGs, or named image sets built from the iconsets), offer a picker
  in Settings, and apply the choice with applicationIconImage on launch.
