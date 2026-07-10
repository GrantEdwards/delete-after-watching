# service.py - Delete Finished Video (v0.0.7)
#
# Kodi 19+ / 21.1 Omega compatible.
#
# Behaviour:
#   - Runs as a background service.
#   - When a video finishes (playback ended), prompts:
#       "Delete finished video?"
#   - Respects add-on settings:
#       * run_for_episodes (bool) - TV episodes
#       * run_for_movies   (bool) - movies
#       * show_delete_list (bool) - show detailed list of items to be deleted
#
#   - If user chooses "Delete":
#       * For TV episodes:
#             - Deletes only the video file (never the folder).
#       * For movies:
#             - Deletes the video file.
#             - If it is the only video file in its folder:
#                   - Deletes the entire folder and all its contents
#                     (artwork, .nfo, subtitles, etc.), with a simple
#                     safety check to avoid deleting generic root
#                     "Movies", "Videos", etc. folders.
#       * Removes the item from Kodi's video library using JSON-RPC.

# service.py - Delete After Watching (v0.0.6 - compact dialog, no textviewer)

import os
import json

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon


ADDON = xbmcaddon.Addon()


class AutoDeletePlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.last_file = None
        self._was_video = False

    def onPlayBackStarted(self):
        self._update_current_file()

    def onAVStarted(self):
        self._update_current_file()

    def onPlayBackEnded(self):
        self._ask_and_delete()

    # def onPlayBackStopped(self):
    #     self._ask_and_delete()

    def _update_current_file(self):
        try:
            self.last_file = self.getPlayingFile()
            self._was_video = self.isPlayingVideo()
        except Exception:
            self.last_file = None
            self._was_video = False

    # ==== JSON-RPC helpers ===================================================

    def _json_rpc(self, payload):
        try:
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            raw = xbmc.executeJSONRPC(payload)
            return json.loads(raw)
        except Exception:
            return {}

    def _get_library_item(self, path):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Files.GetFileDetails",
            "params": {
                "file": path,
                "media": "video",
                "properties": ["file"]
            }
        }

        data = self._json_rpc(request)
        try:
            details = data.get("result", {}).get("filedetails", {})
            item_id = details.get("id")
            item_type = details.get("type")
            if item_id is not None and item_type:
                return item_type, item_id
        except Exception:
            pass

        return None, None

    def _remove_from_library(self, item_type, item_id):
        method = None
        arg_name = None

        if item_type == "movie":
            method = "VideoLibrary.RemoveMovie"
            arg_name = "movieid"
        elif item_type == "episode":
            method = "VideoLibrary.RemoveEpisode"
            arg_name = "episodeid"
        elif item_type == "musicvideo":
            method = "VideoLibrary.RemoveMusicVideo"
            arg_name = "musicvideoid"
        elif item_type == "tvshow":
            method = "VideoLibrary.RemoveTVShow"
            arg_name = "tvshowid"

        if not method or not arg_name:
            return False

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": {arg_name: int(item_id)},
        }

        data = self._json_rpc(request)
        return data.get("result") == "OK"

    # ==== File / folder delete logic ========================================

    @staticmethod
    def _is_leaf_movie_folder(folder_name):
        bad_names = {
            "", "movies", "movie", "films", "film",
            "video", "videos", "media", "tv", "shows", "series"
        }
        return folder_name.lower() not in bad_names

    @staticmethod
    def _join_vfs_path(folder, name):
        return folder.rstrip("/\\") + "/" + name

    def _build_delete_plan(self, path, item_type):
        cleaned = path.rstrip("/\\")
        plan = {
            "file": cleaned,
            "folder_delete": False,
            "folder": None,
            "extra_items": [],
        }

        if item_type != "movie":
            return plan

        folder = os.path.dirname(cleaned)
        if not folder:
            return plan

        dirs, files = xbmcvfs.listdir(folder)
        filename = os.path.basename(cleaned)

        video_exts = (
            ".mkv", ".mp4", ".avi", ".mov", ".flv", ".wmv",
            ".mpeg", ".mpg", ".m4v", ".ts", ".m2ts", ".iso", ".bdmv"
        )
        video_files = [f for f in files if f.lower().endswith(video_exts)]

        video_files_minus_current = [f for f in video_files if f != filename]
        only_video = len(video_files_minus_current) == 0

        if not only_video:
            return plan

        folder_name = folder.rstrip("/\\").split("/")[-1]
        if not self._is_leaf_movie_folder(folder_name):
            return plan

        plan["folder_delete"] = True
        plan["folder"] = folder

        for f in files:
            full = self._join_vfs_path(folder, f)
            if full == cleaned:
                continue
            plan["extra_items"].append(full)

        for d in dirs:
            full_d = self._join_vfs_path(folder, d) + "/"
            plan["extra_items"].append(full_d)

        return plan

    def _log_delete_plan(self, plan):
        xbmc.log("[DeleteAfterWatching] Delete plan begins", level=xbmc.LOGINFO)
        xbmc.log(f"[DeleteAfterWatching] File: {plan['file']}", level=xbmc.LOGINFO)
        if plan["folder_delete"]:
            xbmc.log(
                f"[DeleteAfterWatching] Folder to delete: {plan['folder']}",
                level=xbmc.LOGINFO,
            )
            for p in plan["extra_items"]:
                xbmc.log(
                    f"[DeleteAfterWatching] Folder contents item: {p}",
                    level=xbmc.LOGINFO,
                )
        xbmc.log("[DeleteAfterWatching] Delete plan ends", level=xbmc.LOGINFO)

    def _delete_single_file(self, path):
        return xbmcvfs.delete(path)

    def _delete_movie_and_maybe_folder(self, path):
        cleaned = path.rstrip("/\\")
        folder = os.path.dirname(cleaned)

        file_deleted = xbmcvfs.delete(cleaned)
        if not file_deleted or not folder:
            return file_deleted, False

        dirs, files = xbmcvfs.listdir(folder)

        video_exts = (
            ".mkv", ".mp4", ".avi", ".mov", ".flv", ".wmv",
            ".mpeg", ".mpg", ".m4v", ".ts", ".m2ts", ".iso", ".bdmv"
        )
        video_files = [f for f in files if f.lower().endswith(video_exts)]

        if len(video_files) > 0:
            return True, False

        folder_name = folder.rstrip("/\\").split("/")[-1]
        if not self._is_leaf_movie_folder(folder_name):
            return True, False

        folder_deleted = xbmcvfs.rmdir(folder, True)
        return True, folder_deleted

    # ==== UI / main flow =====================================================

    def _ask_and_delete(self):
        if not self.last_file or not self._was_video:
            return

        path = self.last_file

        if path.startswith("plugin://"):
            return

        if not xbmcvfs.exists(path):
            return

        filename = os.path.basename(path.rstrip("/\\")) or path

        item_type, item_id = self._get_library_item(path)

        run_for_episodes = ADDON.getSettingBool("run_for_episodes")
        run_for_movies = ADDON.getSettingBool("run_for_movies")
        show_delete_list = ADDON.getSettingBool("show_delete_list")

        if item_type == "episode" and not run_for_episodes:
            return
        if item_type == "movie" and not run_for_movies:
            return

        if item_type not in ("episode", "movie"):
            if not (run_for_episodes or run_for_movies):
                return

        plan = self._build_delete_plan(path, item_type)
        if show_delete_list:
            self._log_delete_plan(plan)

        heading = "Delete After Watching"
        line1 = filename

        if item_type == "movie":
            if plan["folder_delete"]:
                line2 = "Delete movie file, its folder, and remove from library?"
            else:
                line2 = "Delete movie file and remove from library?"
        else:
            line2 = "Delete file and remove from library?"

        dialog = xbmcgui.Dialog()

        delete_it = dialog.yesno(
            heading,
            line1+'\n'+line2,
            nolabel="Keep",
            yeslabel="Delete",
        )

        if not delete_it:
            return

        file_deleted = False
        folder_deleted = False

        if item_type == "movie":
            file_deleted, folder_deleted = self._delete_movie_and_maybe_folder(path)
        else:
            file_deleted = self._delete_single_file(path)

        if not file_deleted:
            xbmcgui.Dialog().notification(
                "Delete After Watching",
                "Could not delete file (check SMB permissions).",
                xbmcgui.NOTIFICATION_ERROR,
                4000,
            )
            return

        removed_from_lib = False
        if item_type and item_id is not None:
            removed_from_lib = self._remove_from_library(item_type, item_id)

        msg = f"Deleted: {filename}"
        if folder_deleted:
            msg += " (folder removed)"
        if removed_from_lib:
            msg += " (library updated)"

        xbmcgui.Dialog().notification(
            "Delete After Watching",
            msg,
            xbmcgui.NOTIFICATION_INFO,
            4000,
        )


if __name__ == "__main__":
    monitor = xbmc.Monitor()
    player = AutoDeletePlayer()

    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
