# Delete After Watching (Kodi service add-on)

**Delete After Watching** is a Kodi service add-on that runs in the background and prompts you to delete videos when you finish watching them.

It supports different behaviour for **TV episodes** and **movies**, and can optionally show a detailed preview of everything that will be deleted before you confirm.

---

## Features

- 🧠 **Runs automatically** when Kodi starts (service add-on)
- 🎬 **TV episodes**
  - Prompts after playback finishes
  - Deletes **only the episode file**
  - Removes the episode from the **Kodi video library**
- 🎞️ **Movies**
  - Prompts after playback finishes
  - Deletes the **movie file**
  - If it is the **only video file in its folder**, the add-on:
    - Deletes the **entire folder**
    - Deletes all associated files in that folder (NFO, artwork, subtitles, etc.)
  - Removes the movie from the **Kodi video library**
- 📚 Uses Kodi’s JSON-RPC API to clean up the library entry after deletion
- 🔍 Optional **“preview” dialog** shows everything that will be deleted before you choose Yes

Tested with **Kodi 21 (Omega)** and designed for **Kodi 19+ (Matrix and later)**.

---

## Installation

### Option 1: Install from ZIP (recommended for most users)

1. Download the latest release ZIP from this repository (or use “Download ZIP” and build your own):
   - The ZIP must contain a top-level folder named:

     ```text
     service.delete_finished/
     ```

     with:

     ```text
     service.delete_finished/
       addon.xml
       service.py
       resources/
         settings.xml
     ```

2. Copy the ZIP to a location Kodi can access (local storage, SMB share, etc.).

3. In Kodi:

   - Go to **Settings → Add-ons → Install from zip file**
   - Browse to the ZIP and select it
   - Kodi will install **Delete After Watching** as a **Service** add-on

4. Verify:

   - Go to **Add-ons → My add-ons → Services**
   - You should see **Delete After Watching**
   - Make sure it is **Enabled**

---

## Usage

Once installed and enabled, the add-on runs automatically in the background.

1. Play a video (TV episode or movie) from your usual library.
2. Let it finish playback.
3. When playback ends, the add-on will:
   - Optionally show you a **preview** of what will be deleted
   - Show a **Yes/No dialog** asking if you want to delete the video

If you choose **Delete**:

- For **TV episodes**:
  - The episode file is deleted (via `xbmcvfs.delete`, so SMB/NFS/local are supported)
  - The episode is removed from the Kodi library (using `VideoLibrary.RemoveEpisode`)

- For **movies**:
  - The movie file is deleted
  - If it was the only video file in its folder:
    - The folder and all files under it are deleted (artwork, NFO, subtitles, etc.)
    - A basic safety check prevents deleting generic top-level folders like `Movies`, `Videos`, etc.
  - The movie is removed from the Kodi library (using `VideoLibrary.RemoveMovie`)

A small notification will appear indicating what was deleted and whether the folder and library entry were also removed.

---

## Settings

You can configure the add-on here:

> **Add-ons → My add-ons → Services → Delete After Watching → Configure**

Available settings:

- **Prompt after TV episodes**  
  - When enabled, the add-on prompts to delete after a TV episode finishes.
- **Prompt after movies**  
  - When enabled, the add-on prompts to delete after a movie finishes.
- **Show detailed list of items that will be deleted**  
  - When enabled, a “preview” window appears before the Yes/No dialog, listing:
    - The main file that will be deleted
    - For movies where the folder will also be removed:
      - Other files in the same folder (art, NFO, subtitles, etc.)
      - The folder path that will be deleted

Disable the preview if you prefer a simpler, faster confirmation flow.

---

## Folder deletion rules (movies)

To avoid accidentally deleting large or shared folders, the add-on is conservative about folder removal:

- Only **movies** are allowed to delete their parent folder.
- The folder is only considered for deletion if:
  - After removing the movie file, there are **no other video files** in that folder.
  - The folder name does **not** look like a generic top-level library folder (e.g. `Movies`, `Videos`, `Media`, `TV`, `Series`, etc.).

If those checks fail, only the movie file is deleted; the folder is left intact.

---

## Development

The add-on is implemented as a **Python service** that:

- Subclasses `xbmc.Player` to hook into:
  - `onPlayBackStarted` / `onAVStarted` – to remember the current file
  - `onPlayBackEnded` – to trigger the prompt when playback finishes
- Uses `xbmcvfs` for file operations (works with local paths, SMB, NFS, etc.)
- Uses `xbmc.executeJSONRPC` to:
  - Call `Files.GetFileDetails` and discover the library item type and ID
  - Call `VideoLibrary.RemoveMovie` / `RemoveEpisode` / `RemoveMusicVideo` / `RemoveTVShow`

### Directory layout

```text
service.delete_finished/
  addon.xml          # Kodi add-on manifest
  service.py         # Background service implementation
  resources/
    settings.xml     # Classic Kodi settings definition
